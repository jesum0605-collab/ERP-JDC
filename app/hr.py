import csv
import os
import re
from pathlib import Path
from datetime import date
from io import StringIO

from flask import Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from .db import execute, fetch_all, fetch_one, transaction
from .utils import audit_event, login_required, roles_required

bp = Blueprint("hr", __name__, url_prefix="/rrhh")

# Valores parametrizables para el cálculo inicial. Deben ser revisados por contabilidad
# antes de usar el sistema para liquidaciones legales reales.
SOCIAL_SECURITY_RATES = {
    "eps": 0.04,
    "pension": 0.04,
    "arl": 0.00522,
    "caja": 0.04,
}

NINE_BOX_LABELS = {
    (1, 1): "Bajo desempeño / Bajo potencial",
    (1, 2): "Bajo desempeño / Potencial medio",
    (1, 3): "Bajo desempeño / Alto potencial",
    (2, 1): "Desempeño medio / Bajo potencial",
    (2, 2): "Desempeño medio / Potencial medio",
    (2, 3): "Desempeño medio / Alto potencial",
    (3, 1): "Alto desempeño / Bajo potencial",
    (3, 2): "Alto desempeño / Potencial medio",
    (3, 3): "Alto desempeño / Alto potencial",
}
EVALUATION_QUESTIONS = [
    "Cumple los objetivos y entregables asignados", "Mantiene la calidad esperada en su trabajo",
    "Cumple normas de seguridad y procedimientos", "Trabaja efectivamente con el equipo", "Demuestra responsabilidad y autonomía",
    "Aprende rápidamente nuevas tareas", "Se adapta a cambios y nuevos retos", "Propone mejoras para la operación", "Puede asumir responsabilidades de liderazgo", "Tiene proyección para crecer dentro de la empresa",
]


def _money_value(value):
    """Convierte valores monetarios de planillas/volantes colombianos a float."""
    if value is None:
        return None
    raw = re.sub(r"[^0-9,.-]", "", str(value)).strip()
    if not raw:
        return None
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    elif "." in raw and all(len(part) == 3 for part in raw.split(".")[1:]):
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_slip_values(path, identification=None):
    """Lee valores principales de un volante PDF; devuelve None si no es legible."""
    try:
        from pypdf import PdfReader
        text = "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    except Exception:
        return None
    if identification:
        wanted = re.sub(r"\D", "", str(identification))
        blocks = re.split(r"(?=Nombre\s*:)", text, flags=re.I)
        matching = [block for block in blocks if wanted and wanted in re.sub(r"\D", "", block[:180])]
        if matching:
            text = matching[0]
    patterns = {
        "base_salary": r"salario\s+b[aá]sico\s*[:$]*\s*([\d.,]+)",
        "total_base": r"total\s+base\s*[:$]*\s*([\d.,]+)",
        "biweekly_salary": r"salario\s+quincenal\s*[:$-]*\s*([\d.,]+)",
        "gross": r"(?:total\s+devengos?|devengado|ingresos)\s*[:$]*\s*([\d.,]+)",
        "deductions": r"(?:total\s+deducci[oó]n(?:es)?|deducciones|descuentos)\s*[:$]*\s*([\d.,]+)",
        "net": r"(?:valor\s+a\s+recibir|neto\s+(?:a\s+)?pagar|total\s+neto|neto)\s*[:$]*\s*([\d.,]+)",
    }
    values = {key: _money_value(re.search(pattern, text, re.I).group(1)) for key, pattern in patterns.items() if re.search(pattern, text, re.I)}
    if values.get("gross") is None and values.get("net") is None:
        return None
    gross = values.get("gross") or values.get("net") or 0
    deductions = values.get("deductions")
    net = values.get("net") or round(gross - (deductions or 0), 2)
    transport_matches = re.findall(r"subs\.?\s*transp\.?\s*[:$-]*\s*([\d.,]+)", text, re.I)
    overtime_match = re.search(r"horas\s+extras?\s*[:$-]*\s*([\d.,]+)", text, re.I)
    transport = _money_value(transport_matches[-1]) if transport_matches else 0
    overtime = _money_value(overtime_match.group(1)) if overtime_match else 0
    other = max(0, round(gross - (values.get("biweekly_salary") or 0) - transport - overtime, 2))
    return {
        "base_salary": values.get("base_salary") or 0,
        "total_base": values.get("total_base") or 0,
        "biweekly_salary": values.get("biweekly_salary") or 0,
        "transport_subsidy": transport or 0,
        "overtime": overtime or 0,
        "other_earnings": other,
        "gross": gross,
        "deductions": deductions if deductions is not None else round(gross - net, 2),
        "net": net,
    }


@bp.get("/nomina")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_list():
    periods = fetch_all(
        """
        SELECT pp.*, COUNT(pi.id) AS item_count,
               COALESCE(SUM(pi.net_amount), 0) AS total_net
        FROM payroll_periods pp
        LEFT JOIN payroll_items pi ON pi.payroll_period_id = pp.id
        GROUP BY pp.id ORDER BY pp.period_start DESC
        """
    )
    return render_template("hr/payroll_list.html", periods=periods)


@bp.route("/nomina/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_create():
    if request.method == "POST":
        start = request.form.get("period_start")
        end = request.form.get("period_end")
        if not start or not end or start > end:
            flash("El rango de fechas de la nómina no es válido.", "danger")
        else:
            try:
                period_id = execute(
                    "INSERT INTO payroll_periods (period_start, period_end, payment_date, notes) VALUES (?, ?, ?, ?)",
                    (start, end, request.form.get("payment_date") or None, request.form.get("notes", "").strip() or None),
                ).lastrowid
                audit_event("create", "payroll", "payroll_periods", period_id, after={"period_start": start, "period_end": end, "payment_date": request.form.get("payment_date")})
                flash("Periodo de nómina creado. Ahora puedes calcularlo.", "success")
                return redirect(url_for("hr.payroll_detail", period_id=period_id))
            except Exception:
                flash("El periodo ya existe o los datos no son válidos.", "danger")
    return render_template("hr/payroll_form.html")


@bp.get("/nomina/<int:period_id>")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_detail(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    items = fetch_all(
        """
        SELECT pi.*, e.first_name || ' ' || e.last_name AS employee_name, e.identification_number,
               COALESCE(e.base_salary, 0) AS base_salary
        FROM payroll_items pi LEFT JOIN employees e ON e.id = pi.employee_id
        WHERE pi.payroll_period_id = ? ORDER BY employee_name
        """,
        (period_id,),
    )
    contributions = fetch_all(
        """
        SELECT ssc.*, e.first_name || ' ' || e.last_name AS employee_name,
               COALESCE(eps_ref.name, e.eps, 'No registrada') AS eps_name,
               COALESCE(pension_ref.name, e.pension_fund, 'No registrada') AS pension_name,
               COALESCE(arl_ref.name, e.arl, 'No registrada') AS arl_name
        FROM social_security_contributions ssc
        LEFT JOIN employees e ON e.id = ssc.employee_id
        LEFT JOIN reference_items eps_ref ON eps_ref.id=e.eps_reference_id
        LEFT JOIN reference_items pension_ref ON pension_ref.id=e.pension_fund_reference_id
        LEFT JOIN reference_items arl_ref ON arl_ref.id=e.arl_reference_id
        WHERE ssc.period_start = ? AND ssc.period_end = ? ORDER BY employee_name
        """,
        (period["period_start"], period["period_end"]),
    )
    totals = {
        "gross": sum(float(item["gross_amount"] or 0) for item in items),
        "deductions": sum(float(item["deductions"] or 0) for item in items),
        "net": sum(float(item["net_amount"] or 0) for item in items),
    }
    documents = fetch_all("""
        SELECT pd.*, e.first_name || ' ' || e.last_name AS employee_name
        FROM payroll_documents pd LEFT JOIN employees e ON e.id = pd.employee_id
        WHERE pd.payroll_period_id = ? ORDER BY pd.uploaded_at DESC
    """, (period_id,))
    return render_template("hr/payroll_detail.html", period=period, items=items, contributions=contributions, totals=totals, documents=documents)


@bp.get("/nomina/<int:period_id>/planilla-aportes")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_contributions(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id=?", (period_id,))
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    contributions = fetch_all("""
        SELECT e.identification_number, e.first_name || ' ' || e.last_name AS employee_name,
               COALESCE(eps_ref.name, e.eps, '') AS eps_name,
               COALESCE(pension_ref.name, e.pension_fund, '') AS pension_name,
               COALESCE(arl_ref.name, e.arl, '') AS arl_name,
               ssc.eps_amount, ssc.pension_amount, ssc.arl_amount, ssc.caja_amount
        FROM social_security_contributions ssc
        JOIN employees e ON e.id=ssc.employee_id
        LEFT JOIN reference_items eps_ref ON eps_ref.id=e.eps_reference_id
        LEFT JOIN reference_items pension_ref ON pension_ref.id=e.pension_fund_reference_id
        LEFT JOIN reference_items arl_ref ON arl_ref.id=e.arl_reference_id
        WHERE ssc.period_start=? AND ssc.period_end=? ORDER BY employee_name
    """, (period["period_start"], period["period_end"]))
    return render_template("hr/payroll_contributions.html", period=period, contributions=contributions)


@bp.post("/nomina/<int:period_id>/importar-planilla")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_import(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    upload = request.files.get("planilla")
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    if not upload or not upload.filename.lower().endswith((".csv", ".pdf")):
        flash("Selecciona la planilla original en CSV o PDF.", "danger")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    if upload.filename.lower().endswith(".pdf"):
        folder = Path(current_app.instance_path) / "payroll_documents"
        folder.mkdir(parents=True, exist_ok=True)
        stored = f"{period_id}_planilla_{secure_filename(upload.filename)}"
        upload.save(folder / stored)
        execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND document_type='payroll_sheet'", (period_id,))
        created = execute("INSERT INTO payroll_documents (payroll_period_id, employee_id, document_type, original_name, stored_name, mime_type) VALUES (?, NULL, 'payroll_sheet', ?, ?, 'application/pdf')", (period_id, upload.filename, stored))
        audit_event("import", "payroll", "payroll_documents", created.lastrowid, metadata={"period_id": period_id, "document_type": "payroll_sheet", "original_name": upload.filename})
        flash("Planilla original importada y disponible para visualizar o descargar.", "success")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    try:
        content = upload.stream.read().decode("utf-8-sig")
        reader = csv.DictReader(StringIO(content))
        required = {"identificacion", "devengado", "deducciones", "neto"}
        headers = {str(h or "").strip().lower().replace(" ", "_") for h in (reader.fieldnames or [])}
        if not required.issubset(headers):
            raise ValueError("La planilla debe incluir identificacion, devengado, deducciones y neto.")
        imported = 0
        with transaction():
            for row in reader:
                normalized = {str(k or "").strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()}
                employee = fetch_one("SELECT id FROM employees WHERE identification_number = ? AND deleted_at IS NULL", (normalized["identificacion"],))
                if employee is None:
                    continue
                execute("""
                    INSERT INTO payroll_items (payroll_period_id, employee_id, gross_amount, deductions, net_amount, payment_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT DO NOTHING
                """, (period_id, employee["id"], float(normalized["devengado"] or 0), float(normalized["deducciones"] or 0), float(normalized["neto"] or 0), normalized.get("estado", "pending") or "pending"))
                imported += 1
            execute("UPDATE payroll_periods SET status='calculated', notes=CASE WHEN instr(COALESCE(notes,''), '[SOURCE:PLANILLA]')=0 THEN trim(COALESCE(notes,'') || ' [SOURCE:PLANILLA]') ELSE notes END WHERE id=?", (period_id,))
            audit_event("import", "payroll", "payroll_periods", period_id, metadata={"source": "csv", "imported": imported})
        flash(f"Planilla importada: {imported} registros asociados por identificación.", "success")
    except (ValueError, UnicodeDecodeError) as error:
        flash(f"No se pudo importar la planilla: {error}", "danger")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/volantes")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_upload_slip(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    employee_id = request.form.get("employee_id")
    upload = request.files.get("volante")
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    if not upload or not employee_id or not upload.filename.lower().endswith(".pdf"):
        flash("Selecciona un empleado y un volante PDF válido.", "danger")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    folder = Path(current_app.instance_path) / "payroll_documents"
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{period_id}_{employee_id}_{secure_filename(upload.filename)}"
    destination = folder / stored
    upload.save(destination)
    try:
        with transaction():
            execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND employee_id=? AND document_type='pay_stub'", (period_id, employee_id))
            created = execute("""INSERT INTO payroll_documents (payroll_period_id, employee_id, document_type, original_name, stored_name, mime_type)
                      VALUES (?, ?, 'pay_stub', ?, ?, 'application/pdf')""", (period_id, employee_id, upload.filename, stored))
            audit_event("upload", "payroll", "payroll_documents", created.lastrowid, metadata={"period_id": period_id, "employee_id": employee_id, "document_type": "pay_stub"})
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    flash("Volante de pago cargado correctamente.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/volantes-consolidados")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_upload_consolidated_slips(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    upload = request.files.get("volantes_consolidados")
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    if not upload or not upload.filename.lower().endswith(".pdf"):
        flash("Selecciona un PDF consolidado válido.", "danger")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    folder = Path(current_app.instance_path) / "payroll_documents"
    folder.mkdir(parents=True, exist_ok=True)
    if request.form.get("distribute") == "1":
        try:
            import PIL
            if not getattr(PIL, "__version__", None):
                PIL.__version__ = "13.0.0"
            from pypdf import PdfReader, PdfWriter
            from copy import deepcopy
        except ImportError:
            flash("Falta instalar el componente PDF para distribuir automáticamente los volantes.", "danger")
            return redirect(url_for("hr.payroll_detail", period_id=period_id))
        source = folder / f"_source_{secure_filename(upload.filename)}"
        created_files = []
        records = []
        try:
            upload.save(source)
            reader = PdfReader(str(source))
            distributed = unmatched = 0
            for page_number, original_page in enumerate(reader.pages):
                width, height = float(original_page.mediabox.width), float(original_page.mediabox.height)
                page_text = original_page.extract_text() or ""
                page_ids = re.findall(r"C\.?C\.?\s*#?\s*([0-9][0-9. ]{4,})", page_text, re.I)
                for block, (bottom, top) in enumerate(((height / 2, height), (0, height / 2)), start=1):
                    page = deepcopy(original_page)
                    page.cropbox.lower_left = (0, bottom)
                    page.cropbox.upper_right = (width, top)
                    identification = re.sub(r"\D", "", page_ids[block - 1]) if len(page_ids) >= block else ""
                    employee = fetch_one("SELECT id FROM employees WHERE replace(replace(identification_number, '.', ''), ' ', '') = ? AND deleted_at IS NULL", (identification,)) if identification else None
                    if employee is None:
                        unmatched += 1
                        continue
                    stored = f"{period_id}_{employee['id']}_volante_{page_number + 1}_{block}.pdf"
                    writer = PdfWriter(); writer.add_page(page)
                    with open(folder / stored, "wb") as output:
                        writer.write(output)
                    created_files.append(folder / stored)
                    records.append((employee["id"], f"Volante página {page_number + 1}-{block}.pdf", stored))
                    distributed += 1
            with transaction():
                old_documents = fetch_all("SELECT stored_name FROM payroll_documents WHERE payroll_period_id=? AND document_type='pay_stub'", (period_id,))
                execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND document_type='pay_stub'", (period_id,))
                for employee_id, original_name, stored in records:
                    execute("INSERT INTO payroll_documents (payroll_period_id, employee_id, document_type, original_name, stored_name, mime_type) VALUES (?, ?, 'pay_stub', ?, ?, 'application/pdf')", (period_id, employee_id, original_name, stored))
                audit_event("distribute", "payroll", "payroll_periods", period_id, metadata={"distributed": distributed, "unmatched": unmatched})
            for old in old_documents:
                if old["stored_name"] not in {record[2] for record in records}:
                    (folder / old["stored_name"]).unlink(missing_ok=True)
            source.unlink(missing_ok=True)
        except Exception:
            for path in created_files:
                path.unlink(missing_ok=True)
            source.unlink(missing_ok=True)
            raise
        flash(f"Distribución terminada: {distributed} volantes asociados. {unmatched} bloques requieren revisión.", "success" if distributed else "warning")
        return redirect(url_for("hr.payroll_detail", period_id=period_id))
    stored = f"{period_id}_consolidado_{secure_filename(upload.filename)}"
    upload.save(folder / stored)
    execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND document_type='payroll_sheet'", (period_id,))
    created = execute("""INSERT INTO payroll_documents (payroll_period_id, employee_id, document_type, original_name, stored_name, mime_type)
              VALUES (?, NULL, 'payroll_sheet', ?, ?, 'application/pdf')""", (period_id, upload.filename, stored))
    audit_event("upload", "payroll", "payroll_documents", created.lastrowid, metadata={"period_id": period_id, "document_type": "payroll_sheet", "original_name": upload.filename})
    flash("Volantes consolidados cargados correctamente para todo el periodo.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.get("/nomina/documentos/<int:document_id>")
@login_required
def payroll_document(document_id):
    document = fetch_one("SELECT pd.*, e.identification_number FROM payroll_documents pd LEFT JOIN employees e ON e.id=pd.employee_id WHERE pd.id=?", (document_id,))
    if document is None:
        return render_template("error.html", code=404, message="Documento no encontrado."), 404
    manager_roles = {"admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo"}
    current_roles = {row["name"] for row in g.get("user_roles", [])}
    if not current_roles.intersection(manager_roles) and document["identification_number"] != g.user["username"]:
        abort(403)
    return send_from_directory(Path(current_app.instance_path) / "payroll_documents", document["stored_name"], as_attachment=False, download_name=document["original_name"])


@bp.post("/nomina/<int:period_id>/eliminar-corte")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_delete_cut(period_id):
    documents = fetch_all("SELECT stored_name FROM payroll_documents WHERE payroll_period_id=? AND document_type='pay_stub'", (period_id,))
    folder = Path(current_app.instance_path) / "payroll_documents"
    for document in documents:
        try:
            (folder / document["stored_name"]).unlink()
        except OSError:
            pass
    with transaction():
        execute("DELETE FROM payroll_documents WHERE payroll_period_id=? AND document_type='pay_stub'", (period_id,))
        audit_event("delete_cut", "payroll", "payroll_documents", period_id, metadata={"deleted_documents": len(documents), "document_type": "pay_stub"})
    flash(f"Corte eliminado. Se retiraron {len(documents)} volantes individuales; el PDF consolidado se conservó.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/calcular")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_calculate(period_id):
    # El cálculo toca liquidaciones, aportes y estado del período: todo debe
    # confirmarse o revertirse como una única operación.
    with transaction():
        return _payroll_calculate_impl(period_id)


def _payroll_calculate_impl(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id = ?", (period_id,))
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    start = date.fromisoformat(period["period_start"])
    end = date.fromisoformat(period["period_end"])
    days = (end - start).days + 1
    employees = fetch_all(
        "SELECT * FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY last_name, first_name"
    )
    execute(
        "DELETE FROM social_security_contributions WHERE period_start = ? AND period_end = ?",
        (period["period_start"], period["period_end"]),
    )
    imported_items = {}
    if "[SOURCE:PLANILLA]" in (period["notes"] or ""):
        imported_items = {
            row["employee_id"]: row for row in fetch_all(
                "SELECT * FROM payroll_items WHERE payroll_period_id=? AND employee_id IS NOT NULL", (period_id,)
            )
        }
    # Un empleado debe tener una sola liquidación por período. Las versiones
    # anteriores insertaban otra fila cada vez que se pulsaba Calcular.
    execute("""
        DELETE FROM payroll_items
        WHERE payroll_period_id=? AND id NOT IN (
            SELECT MIN(id) FROM payroll_items
            WHERE payroll_period_id=? GROUP BY employee_id
        )
    """, (period_id, period_id))
    current_items = {
        row["employee_id"]: row for row in fetch_all(
            "SELECT * FROM payroll_items WHERE payroll_period_id=? AND employee_id IS NOT NULL",
            (period_id,),
        )
    }
    slip_values = {}
    documents = fetch_all(
        "SELECT employee_id, stored_name FROM payroll_documents WHERE payroll_period_id=? AND document_type='pay_stub' AND employee_id IS NOT NULL",
        (period_id,),
    )
    document_folder = Path(current_app.instance_path) / "payroll_documents"
    for document in documents:
        employee = fetch_one("SELECT identification_number FROM employees WHERE id=?", (document["employee_id"],))
        values = _extract_slip_values(document_folder / document["stored_name"], employee["identification_number"] if employee else None)
        if values:
            slip_values[document["employee_id"]] = values
    sources = {"planilla": 0, "volante": 0, "pendiente": 0}
    for employee in employees:
        source = "sistema"
        components = {"base_salary": 0, "total_base": 0, "biweekly_salary": 0, "transport_subsidy": 0, "overtime": 0, "other_earnings": 0}
        if employee["id"] in imported_items:
            values = imported_items[employee["id"]]
            gross = float(values["gross_amount"] or 0)
            deductions = float(values["deductions"] or 0)
            net = float(values["net_amount"] or 0)
            source = "planilla"
        elif employee["id"] in slip_values:
            values = slip_values[employee["id"]]
            gross, deductions, net = values["gross"], values["deductions"], values["net"]
            components = values
            source = "volante"
        else:
            # El salario base es contractual y no representa una liquidación.
            # Sin planilla ni volante, dejamos el registro en cero para revisión.
            gross = deductions = net = 0
            source = "pendiente"
        sources[source] += 1
        eps = round(gross * SOCIAL_SECURITY_RATES["eps"], 2)
        pension = round(gross * SOCIAL_SECURITY_RATES["pension"], 2)
        arl = round(gross * SOCIAL_SECURITY_RATES["arl"], 2)
        caja = round(gross * SOCIAL_SECURITY_RATES["caja"], 2)
        # Las deducciones y el neto pertenecen al volante/planilla importado.
        # No se reemplazan por una estimación de EPS + pensión: esos aportes
        # se muestran por separado en seguridad social.
        if employee["id"] in current_items:
            execute("""UPDATE payroll_items SET gross_amount=?, deductions=?, net_amount=?,
                base_salary_amount=?, total_base_amount=?, biweekly_salary_amount=?,
                transport_subsidy_amount=?, overtime_amount=?, other_earnings_amount=? WHERE id=?""",
                    (gross, deductions, net, components["base_salary"], components["total_base"], components["biweekly_salary"],
                     components["transport_subsidy"], components["overtime"], components["other_earnings"], current_items[employee["id"]]["id"]))
        else:
            execute("""
                INSERT INTO payroll_items (payroll_period_id, employee_id, gross_amount, deductions, net_amount,
                    base_salary_amount, total_base_amount, biweekly_salary_amount, transport_subsidy_amount,
                    overtime_amount, other_earnings_amount, payment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (period_id, employee["id"], gross, deductions, net, components["base_salary"], components["total_base"],
                   components["biweekly_salary"], components["transport_subsidy"], components["overtime"], components["other_earnings"]))
        execute(
            """
            INSERT INTO social_security_contributions
            (period_start, period_end, employee_id, eps_amount, pension_amount, arl_amount, caja_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (period["period_start"], period["period_end"], employee["id"], eps, pension, arl, caja),
        )
    execute("UPDATE payroll_periods SET status='calculated' WHERE id = ?", (period_id,))
    audit_event("calculate", "payroll", "payroll_periods", period_id, after={"status": "calculated", "sources": sources})
    flash(f"Nómina calculada con planilla: {sources['planilla']}, volantes: {sources['volante']} y pendientes de soporte: {sources['pendiente']}. El salario base no se usa como devengado.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/cerrar")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_close(period_id):
    with transaction():
        before = fetch_one("SELECT status FROM payroll_periods WHERE id=?", (period_id,))
        execute("UPDATE payroll_periods SET status='closed' WHERE id = ? AND status='calculated'", (period_id,))
        after = fetch_one("SELECT status FROM payroll_periods WHERE id=?", (period_id,))
        if before and after and before["status"] != after["status"]:
            audit_event("close", "payroll", "payroll_periods", period_id, before=dict(before), after=dict(after))
    flash("Periodo de nómina cerrado.", "success")
    return redirect(url_for("hr.payroll_detail", period_id=period_id))


@bp.post("/nomina/<int:period_id>/eliminar")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa")
def payroll_delete(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id=?", (period_id,))
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    documents = fetch_all("SELECT stored_name FROM payroll_documents WHERE payroll_period_id=?", (period_id,))
    folder = Path(current_app.instance_path) / "payroll_documents"
    for document in documents:
        try:
            (folder / document["stored_name"]).unlink(missing_ok=True)
        except OSError:
            pass
    with transaction():
        execute("DELETE FROM payroll_documents WHERE payroll_period_id=?", (period_id,))
        execute("DELETE FROM payroll_items WHERE payroll_period_id=?", (period_id,))
        execute("DELETE FROM social_security_contributions WHERE period_start=? AND period_end=?", (period["period_start"], period["period_end"]))
        execute("DELETE FROM payroll_periods WHERE id=?", (period_id,))
        audit_event("delete", "payroll", "payroll_periods", period_id, before={"period_start": period["period_start"], "period_end": period["period_end"]})
    flash("Periodo de nómina y sus soportes eliminados.", "success")
    return redirect(url_for("hr.payroll_list"))


@bp.get("/nomina/<int:period_id>/planilla.csv")
@login_required
@roles_required("admin", "gerencia", "rrhh", "asistente_administrativa", "coordinador_operativo")
def payroll_social_security_csv(period_id):
    period = fetch_one("SELECT * FROM payroll_periods WHERE id=?", (period_id,))
    if period is None:
        return render_template("error.html", code=404, message="Periodo de nómina no encontrado."), 404
    rows = fetch_all(
        """
        SELECT e.identification_number, e.first_name || ' ' || e.last_name AS employee_name,
               COALESCE(eps_ref.name, e.eps, '') AS eps_name,
               COALESCE(pension_ref.name, e.pension_fund, '') AS pension_name,
               COALESCE(arl_ref.name, e.arl, '') AS arl_name,
               ssc.eps_amount, ssc.pension_amount,
               ssc.arl_amount, ssc.caja_amount, ssc.status
        FROM social_security_contributions ssc
        JOIN employees e ON e.id=ssc.employee_id
        LEFT JOIN reference_items eps_ref ON eps_ref.id=e.eps_reference_id
        LEFT JOIN reference_items pension_ref ON pension_ref.id=e.pension_fund_reference_id
        LEFT JOIN reference_items arl_ref ON arl_ref.id=e.arl_reference_id
        WHERE ssc.period_start=? AND ssc.period_end=?
        ORDER BY employee_name
        """,
        (period["period_start"], period["period_end"]),
    )
    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "Identificación", "Empleado", "EPS", "Fondo pensión", "ARL",
        "Aporte EPS", "Aporte pensión", "Aporte ARL", "Caja", "Estado",
    ])
    for row in rows:
        writer.writerow([
            row["identification_number"], row["employee_name"], row["eps_name"] or "",
            row["pension_name"] or "", row["arl_name"] or "", row["eps_amount"],
            row["pension_amount"], row["arl_amount"], row["caja_amount"], row["status"],
        ])
    filename = f"planilla-seguridad-social-{period['period_start']}-{period['period_end']}.csv"
    return Response(
        output.getvalue(), mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.get("/evaluaciones-9box")
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def evaluation_list():
    evaluations = fetch_all(
        """
        SELECT pe.*, e.first_name || ' ' || e.last_name AS employee_name,
               u.full_name AS evaluator_name
        FROM performance_evaluations pe
        JOIN employees e ON e.id = pe.employee_id
        LEFT JOIN users u ON u.id = pe.evaluator_user_id
        ORDER BY pe.evaluation_date DESC, employee_name
        """
    )
    history = {}
    for evaluation in evaluations:
        history.setdefault(evaluation["employee_id"], []).append(evaluation)
    return render_template("hr/evaluations.html", evaluations=evaluations, history=history, labels=NINE_BOX_LABELS)


@bp.route("/evaluaciones-9box/nueva", methods=("GET", "POST"))
@login_required
@roles_required("admin", "gerencia", "rrhh", "coordinador_operativo", "supervisor_operaciones")
def evaluation_create():
    employees = fetch_all(
        "SELECT id, first_name || ' ' || last_name AS name, position FROM employees WHERE status='active' AND deleted_at IS NULL ORDER BY name"
    )
    if request.method == "POST":
        answers = [int(request.form.get(f"question_{i}", 0)) for i in range(1, 11)]
        performance = round(sum(answers[:5]) / 5) if all(1 <= value <= 3 for value in answers) else 0
        potential = round(sum(answers[5:]) / 5) if all(1 <= value <= 3 for value in answers) else 0
        if performance not in (1, 2, 3) or potential not in (1, 2, 3):
            flash("El desempeño y el potencial deben estar entre 1 y 3.", "danger")
        else:
            cell = NINE_BOX_LABELS[(performance, potential)]
            created = execute(
                """
                INSERT INTO performance_evaluations
                (employee_id, evaluation_date, evaluator_user_id, performance_score, potential_score,
                 nine_box_cell, strengths, development_plan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.form.get("employee_id"), request.form.get("evaluation_date") or date.today().isoformat(),
                    g.user["id"], performance, potential, cell,
                    request.form.get("strengths", "").strip() or None,
                    request.form.get("development_plan", "").strip() or None,
                ),
            )
            for number, score in enumerate(answers, 1):
                execute("INSERT INTO performance_evaluation_answers (evaluation_id, question_number, answer_score) VALUES (?, ?, ?)", (created.lastrowid, number, score))
            audit_event("create", "hr", "performance_evaluations", created.lastrowid, after={"employee_id": request.form.get("employee_id"), "performance_score": performance, "potential_score": potential, "nine_box_cell": cell})
            flash("Evaluación 9-Box registrada.", "success")
            return redirect(url_for("hr.evaluation_list"))
    return render_template("hr/evaluation_form.html", employees=employees, evaluation_questions=EVALUATION_QUESTIONS)
