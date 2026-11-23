import json
import re
import uuid
import zipfile
import html
from datetime import date
from pathlib import Path

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from .db import execute, fetch_all, fetch_one
from .utils import audit_event, login_required, roles_required

bp = Blueprint("documents", __name__, url_prefix="/documentos")
MANAGER_ROLES = ("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
ALLOWED = {"pdf", "docx", "html", "htm", "txt"}


def _folder():
    folder = Path(current_app.instance_path) / "documents"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


_UNITS = ("cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte")
_TENS = ("", "", "veinti", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")


def _number_words(value):
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return str(value or "")
    if n < 0:
        return "menos " + _number_words(-n)
    if n <= 20:
        return _UNITS[n]
    if n < 30:
        return "veinti" + _UNITS[n - 20]
    if n < 100:
        return _TENS[n // 10] + (" y " + _UNITS[n % 10] if n % 10 else "")
    if n < 1000:
        hundreds = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}
        if n == 100: return "cien"
        return hundreds[n // 100] + (" " + _number_words(n % 100) if n % 100 else "")
    if n < 1000000:
        thousands = n // 1000
        prefix = "mil" if thousands == 1 else _number_words(thousands) + " mil"
        return prefix + (" " + _number_words(n % 1000) if n % 1000 else "")
    millions = n // 1000000
    prefix = "un millón" if millions == 1 else _number_words(millions) + " millones"
    return prefix + (" " + _number_words(n % 1000000) if n % 1000000 else "")


def _date_words(raw):
    if not raw:
        return ""
    try:
        parsed = date.fromisoformat(raw)
        months = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        return f"{_number_words(parsed.day)} ({parsed.day}) de {months[parsed.month - 1]} de {_number_words(parsed.year)} ({parsed.year})"
    except ValueError:
        return raw


def _employee_context(employee):
    values = dict(employee)
    values["full_name"] = f"{employee['first_name']} {employee['last_name']}"
    values["document"] = employee["identification_number"]
    values["position"] = employee["position"] or ""
    today = date.today()
    values["issue_day"] = today.day
    values["issue_month"] = today.strftime("%B")
    values["issue_year"] = today.year
    return values


def _docx_to_pdf(source_path, output_path, values):
    """Reemplaza marcadores del DOCX y usa Word instalado para exportar a PDF."""
    import tempfile
    import win32com.client
    markers = {
        "[NOMBRES Y APELLIDOS]": values.get("full_name", ""),
        "[TIPO DE DOCUMENTO]": values.get("document_type", "CC"),
        "[NÚMERO DE IDENTIFÍCACIÓN]": values.get("document", ""),
        "[N�MERO DE IDENTIF�CACI�N]": values.get("document", ""),
        "[fecha de ingreso en letras y números]": values.get("hire_date", ""),
        "[SALARIO BASE EN LETRAS": str(values.get("base_salary", "")),
        "[DÍAS EN LETRAS (": "",
        "[mes]": "",
        "[AÑO EN LETRAS": "",
    }
    def replace_marker(match):
        marker = match.group(0)
        label = marker.strip("[] ").lower()
        if "nombre" in label or "apellido" in label:
            return str(values.get("full_name", ""))
        if "salario" in label or "sueldo" in label:
            return str(values.get("base_salary", ""))
        if "fecha de ingreso" in label:
            return str(values.get("hire_date", ""))
        if "hasta la fecha" in label:
            return "la fecha"
        if "días" in label or "dias" in label:
            return str(values.get("issue_day", ""))
        if "mes" in label:
            return str(values.get("issue_month", ""))
        if "año" in label or "ano" in label:
            return str(values.get("issue_year", ""))
        if "tipo de documento" in label:
            return str(values.get("document_type", "CC"))
        if "cargo" in label:
            return str(values.get("position", ""))
        if "número" in label or "numero" in label or "identific" in label:
            return str(values.get("document", ""))
        return marker
    with tempfile.TemporaryDirectory(prefix="jdc_docx_") as temp:
        working = Path(temp) / "document.docx"
        with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(working, "w") as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename == "word/document.xml":
                    text = data.decode("utf-8")
                    text = re.sub(r"\[[^\]]+\]", replace_marker, text, flags=re.IGNORECASE)
                    for marker, value in markers.items():
                        text = text.replace(marker, str(value or ""))
                    data = text.encode("utf-8")
                target.writestr(item, data)
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(working.resolve()))
        try:
            doc.ExportAsFixedFormat(str(output_path.resolve()), 17)
        finally:
            doc.Close(False)
            word.Quit()


def _build_certificate_pdf(output_path, values):
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    base = Path(current_app.instance_path) / "documents" / "certificado_laboral_base.pdf"
    if not base.exists():
        raise FileNotFoundError("No existe la plantilla base del certificado laboral.")
    overlay = BytesIO()
    c = canvas.Canvas(overlay, pagesize=letter)
    # Cubrimos únicamente el cuerpo variable del certificado, conservando membrete y pie.
    c.setFillColorRGB(1, 1, 1)
    # La plantilla conserva el membrete, pero trae texto de ejemplo. Cubrimos
    # todo el bloque textual anterior para que nunca se mezcle con el nuevo.
    c.rect(78, 55, 465, 500, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 10.5)
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_JUSTIFY
    styles = getSampleStyleSheet(); style = styles["Normal"]; style.fontName="Helvetica"; style.fontSize=10.5; style.leading=15; style.alignment=TA_JUSTIFY
    paragraph = (f"Mediante la presente certificamos que el señor <b>{html.escape(values['full_name'])}</b>, "
        f"identificado con {values['document_type']} número {values['document']}, expedida en {values['city']}, "
        f"labora en nuestra empresa desde el {values['hire_date']} hasta la fecha, desempeñando el cargo de "
        f"{values['position']}, devengando un salario de {values['salary']} con un contrato {values['contract_type']}.")
    body = Paragraph(paragraph, style); body.wrapOn(c, 465, 120); body.drawOn(c, 78, 425)
    second = "Durante este tiempo ha demostrado ser una persona seria, honesta y responsable en el desempeño de sus funciones."
    body = Paragraph(second, style); body.wrapOn(c, 465, 45); body.drawOn(c, 78, 365)
    third = f"El presente certificado se expide a solicitud del interesado en la ciudad de {values['city']} a los {values['issue_date']}."
    body = Paragraph(third, style); body.wrapOn(c, 465, 45); body.drawOn(c, 78, 310)
    c.setStrokeColorRGB(0.15, 0.15, 0.15); c.setLineWidth(0.7); c.line(78, 190, 220, 190)
    c.setFont("Helvetica-Bold", 9.5); c.drawString(78, 176, "Encargado:")
    c.drawString(78, 154, "Dpto. de Recursos Humanos")
    note = "Nota: para su validez, este documento debe contar con la firma del encargado de turno."
    note_style = styles["Normal"]; note_style.fontName="Helvetica"; note_style.fontSize=8.5; note_style.leading=12
    note_para = Paragraph(note, note_style); note_para.wrapOn(c, 250, 35); note_para.drawOn(c, 78, 82)
    c.save(); overlay.seek(0)
    page = PdfReader(str(base)).pages[0]; page.merge_page(PdfReader(overlay).pages[0])
    writer = PdfWriter(); writer.add_page(page)
    with output_path.open("wb") as stream: writer.write(stream)


@bp.get("")
@login_required
@roles_required(*MANAGER_ROLES)
def index():
    templates = fetch_all("SELECT t.*, u.full_name AS uploader FROM document_templates t LEFT JOIN users u ON u.id=t.uploaded_by WHERE t.is_active=1 ORDER BY t.created_at DESC")
    generated = fetch_all("""SELECT d.*, t.name AS template_name, e.first_name || ' ' || e.last_name AS employee_name
        FROM generated_documents d JOIN document_templates t ON t.id=d.template_id JOIN employees e ON e.id=d.employee_id
        ORDER BY d.created_at DESC LIMIT 100""")
    return render_template("documents/index.html", templates=templates, generated=generated)


@bp.route("/certificado-laboral", methods=("GET", "POST"))
@login_required
@roles_required("gerencia", "coordinador_operativo", "asistente_administrativa")
def labor_certificate():
    employees = fetch_all("""SELECT id, first_name || ' ' || last_name AS name, identification_number,
        document_type, position, hire_date, base_salary FROM employees
        WHERE status='active' AND deleted_at IS NULL ORDER BY last_name, first_name""")
    if request.method == "POST":
        employee = fetch_one("SELECT * FROM employees WHERE id=? AND status='active' AND deleted_at IS NULL", (request.form.get("employee_id"),))
        if not employee:
            flash("Selecciona un colaborador válido.", "danger")
            return render_template("documents/certificate_form.html", employees=employees)
        values = {
            "full_name": f"{employee['first_name']} {employee['last_name']}",
            "document_type": request.form.get("document_type") or employee["document_type"] or "Cédula de ciudadanía",
            "document": employee["identification_number"], "city": request.form.get("city", "Cartagena").strip(),
            "hire_date": _date_words(request.form.get("hire_date") or employee["hire_date"] or "") or "la fecha indicada",
            "position": request.form.get("position") or employee["position"] or "colaborador",
            "salary": (f"{_number_words(request.form.get('salary', '').strip())} pesos ($" + f"{float(request.form.get('salary', '').strip()):,.0f})") if request.form.get("salary", "").strip() else (f"{_number_words(employee['base_salary'] or 0)} pesos ($" + f"{float(employee['base_salary'] or 0):,.0f})"),
            "contract_type": request.form.get("contract_type", "a término indefinido"),
            "issue_date": _date_words(request.form.get("issue_date", "").strip()) or "la fecha de expedición",
        }
        filename = secure_filename(f"certificado_laboral_{values['full_name']}.pdf")
        stored = f"certificate_{g.user['id']}_{employee['id']}_{uuid.uuid4().hex}_{filename}"
        _build_certificate_pdf(_folder() / stored, values)
        template = fetch_one("SELECT id FROM document_templates WHERE name='Certificado laboral (formulario)' ORDER BY id LIMIT 1")
        if template:
            template_id = template["id"]
            execute("UPDATE document_templates SET is_active=1 WHERE id=?", (template_id,))
        else:
            template_id = execute("INSERT INTO document_templates (name, description, original_name, stored_name, mime_type, uploaded_by) VALUES (?, ?, ?, ?, ?, ?)", ("Certificado laboral (formulario)", "Generado mediante formulario", "certificado_laboral_base.pdf", "certificate-base", "application/pdf", g.user["id"])).lastrowid
        created = execute("INSERT INTO generated_documents (template_id, employee_id, original_name, stored_name, generated_by) VALUES (?, ?, ?, ?, ?)", (template_id, employee["id"], filename, stored, g.user["id"]))
        audit_event("generate", "documents", "generated_documents", created.lastrowid, metadata={"template_id": template_id, "employee_id": employee["id"], "original_name": filename})
        flash("Certificado laboral generado correctamente.", "success")
        return redirect(url_for("documents.download_generated", document_id=created.lastrowid))
    return render_template("documents/certificate_form.html", employees=employees)


@bp.post("/plantillas")
@login_required
@roles_required(*MANAGER_ROLES)
def template_upload():
    upload = request.files.get("template")
    name = request.form.get("name", "").strip()
    if not upload or not upload.filename or not name:
        flash("Indica un nombre y selecciona una plantilla.", "danger")
        return redirect(url_for("documents.index"))
    extension = Path(upload.filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED:
        flash("La plantilla debe ser PDF, DOCX, HTML o TXT.", "danger")
        return redirect(url_for("documents.index"))
    mapping = request.form.get("field_mapping", "").strip() or None
    if mapping:
        try:
            json.loads(mapping)
        except json.JSONDecodeError:
            flash("La asignación de campos debe ser un JSON válido.", "danger")
            return redirect(url_for("documents.index"))
    stored = f"template_{g.user['id']}_{uuid.uuid4().hex}_{secure_filename(upload.filename)}"
    upload.save(_folder() / stored)
    created = execute("INSERT INTO document_templates (name, description, original_name, stored_name, mime_type, field_mapping, uploaded_by) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, request.form.get("description", "").strip() or None, upload.filename, stored, upload.mimetype, mapping, g.user["id"]))
    audit_event("upload", "documents", "document_templates", created.lastrowid, after={"name": name, "original_name": upload.filename, "mime_type": upload.mimetype})
    flash("Plantilla cargada. Si es PDF con campos AcroForm, se rellenará automáticamente.", "success")
    return redirect(url_for("documents.index"))


@bp.get("/plantillas/<int:template_id>/generar")
@login_required
@roles_required(*MANAGER_ROLES)
def generate_form(template_id):
    template = fetch_one("SELECT * FROM document_templates WHERE id=? AND is_active=1", (template_id,))
    if not template:
        return render_template("error.html", code=404, message="Plantilla no encontrada."), 404
    employees = fetch_all("SELECT id, first_name || ' ' || last_name AS name, identification_number, position FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY last_name, first_name")
    return render_template("documents/generate.html", template=template, employees=employees)


@bp.post("/plantillas/<int:template_id>/eliminar")
@login_required
@roles_required(*MANAGER_ROLES)
def template_delete(template_id):
    template = fetch_one("SELECT * FROM document_templates WHERE id=?", (template_id,))
    if not template:
        flash("Plantilla no encontrada.", "danger")
        return redirect(url_for("documents.index"))
    used = fetch_one("SELECT COUNT(*) AS total FROM generated_documents WHERE template_id=?", (template_id,))["total"]
    if used:
        execute("UPDATE document_templates SET is_active=0 WHERE id=?", (template_id,))
        audit_event("archive", "documents", "document_templates", template_id, before={"is_active": template["is_active"]}, after={"is_active": 0}, reason="template_has_generated_documents")
        flash("La plantilla fue archivada porque ya tiene documentos generados. El historial se conserva.", "warning")
    else:
        (_folder() / template["stored_name"]).unlink(missing_ok=True)
        execute("DELETE FROM document_templates WHERE id=?", (template_id,))
        audit_event("delete", "documents", "document_templates", template_id, before={"name": template["name"], "stored_name": template["stored_name"]})
        flash("Plantilla eliminada correctamente.", "success")
    return redirect(url_for("documents.index"))


@bp.post("/plantillas/<int:template_id>/generar")
@login_required
@roles_required(*MANAGER_ROLES)
def generate(template_id):
    template = fetch_one("SELECT * FROM document_templates WHERE id=? AND is_active=1", (template_id,))
    employee = fetch_one("""SELECT e.*, eps.name AS eps_display, arl.name AS arl_display, p.name AS pension_display
        FROM employees e LEFT JOIN reference_items eps ON eps.id=e.eps_reference_id
        LEFT JOIN reference_items arl ON arl.id=e.arl_reference_id LEFT JOIN reference_items p ON p.id=e.pension_fund_reference_id
        WHERE e.id=? AND e.deleted_at IS NULL""", (request.form.get("employee_id"),))
    if not template or not employee:
        return render_template("error.html", code=404, message="Plantilla o colaborador no encontrado."), 404
    values = _employee_context(employee)
    source_path = _folder() / template["stored_name"]
    if Path(template["original_name"]).suffix.lower() == ".docx":
        filename = secure_filename(f"{template['name']}_{values['full_name']}.pdf")
        stored = f"generated_{g.user['id']}_{employee['id']}_{template_id}_{uuid.uuid4().hex}_{filename}"
        try:
            _docx_to_pdf(source_path, _folder() / stored, values)
        except Exception:
            flash("La plantilla DOCX fue recibida, pero la conversión a PDF requiere que Microsoft Word esté disponible en una sesión de escritorio activa.", "danger")
            return redirect(url_for("documents.generate_form", template_id=template_id))
    elif Path(template["original_name"]).suffix.lower() == ".pdf":
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(source_path))
        form_fields = reader.get_fields() or {}
        if not form_fields:
            flash("Este PDF no tiene campos rellenables AcroForm. Debes cargar una versión editable del formato o configurar posiciones de impresión antes de generarlo.", "danger")
            return redirect(url_for("documents.generate_form", template_id=template_id))
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        writer.set_need_appearances_writer()
        mapping = json.loads(template["field_mapping"] or "{}")
        fields = {field: str(values.get(mapping.get(field, field), "") or "") for field in form_fields}
        for page in writer.pages:
            writer.update_page_form_field_values(page, fields, auto_regenerate=False)
        filename = secure_filename(f"{template['name']}_{values['full_name']}.pdf")
        stored = f"generated_{g.user['id']}_{employee['id']}_{template_id}_{uuid.uuid4().hex}_{filename}"
        with ( _folder() / stored).open("wb") as output:
            writer.write(output)
    else:
        source = source_path.read_text(encoding="utf-8")
        rendered = source
        for key, value in values.items():
            rendered = rendered.replace("{{ employee." + key + " }}", str(value or ""))
        filename = secure_filename(f"{template['name']}_{values['full_name']}.html")
        stored = f"generated_{g.user['id']}_{employee['id']}_{template_id}_{uuid.uuid4().hex}_{filename}"
        ( _folder() / stored).write_text(rendered, encoding="utf-8")
    created = execute("INSERT INTO generated_documents (template_id, employee_id, original_name, stored_name, generated_by) VALUES (?, ?, ?, ?, ?)", (template_id, employee["id"], filename, stored, g.user["id"]))
    audit_event("generate", "documents", "generated_documents", created.lastrowid, metadata={"template_id": template_id, "employee_id": employee["id"], "original_name": filename})
    flash("Documento generado con los datos del colaborador.", "success")
    return redirect(url_for("documents.download_generated", document_id=created.lastrowid))


@bp.get("/generados/<int:document_id>")
@login_required
def download_generated(document_id):
    document = fetch_one("SELECT d.*, e.identification_number FROM generated_documents d JOIN employees e ON e.id=d.employee_id WHERE d.id=?", (document_id,))
    if not document:
        return render_template("error.html", code=404, message="Documento no encontrado."), 404
    if not any(row["name"] in MANAGER_ROLES for row in g.get("user_roles", [])) and document["identification_number"] != g.user["username"]:
        return render_template("error.html", code=403, message="No tienes permisos para ver este documento."), 403
    return send_from_directory(_folder(), document["stored_name"], as_attachment=False, download_name=document["original_name"])
