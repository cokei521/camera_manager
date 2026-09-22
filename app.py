"""
相机地址管理系统 - Flask 主应用
"""
import os
import re
import logging
from datetime import date
from io import BytesIO

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_file, make_response
)
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

from models import db, Camera
from utils import natural_sort_key, parse_batch_codes, format_coordinate

# ─── 日志配置 ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Flask 应用初始化 ────────────────────────────────
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///camera.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ─── 首页 / 列表 ─────────────────────────────────────
@app.route('/')
def index():
    """首页：相机列表，支持分页、搜索、排序"""
    page = request.args.get('page', 1, type=int)
    per_page = 300
    search = request.args.get('search', '').strip()

    query = Camera.query

    if search:
        query = query.filter(
            db.or_(
                Camera.ip_address.contains(search),
                Camera.name_751_2024.contains(search),
                Camera.code.contains(search),
                Camera.maintenance_unit.contains(search),
                Camera.maintenance_person.contains(search),
                Camera.district.contains(search),
            )
        )

    # 按编码排序（SQLite 自然排序）
    query = query.order_by(Camera.code)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    cameras = pagination.items

    # 可定制显示的列（默认全部显示，通过 columns 参数控制）
    default_columns = [
        'code', 'name_751_2024', 'ip_address', 'longitude', 'latitude',
        'location', 'district'
    ]
    selected_columns = request.args.getlist('columns')
    if not selected_columns:
        selected_columns = default_columns

    all_columns = [
        ('code', '相机编码'),
        ('name_751_2024', '相机名称（751-2024）'),
        ('name_751_2008', '相机名称（751-2008）'),
        ('ip_address', 'IP地址'),
        ('longitude', '经度'),
        ('latitude', '纬度'),
        ('location', '地理位置'),
        ('district', '所属辖区'),
        ('camera_type', '相机类型'),
        ('operator', '运营商'),
        ('maintenance_unit', '运维单位'),
        ('maintenance_person', '运维人员'),
        ('maintenance_phone', '运维人员电话'),
        ('unit_manager', '运维单位责任人'),
        ('manager_phone', '单位责任人电话'),
        ('update_date', '更新日期'),
        ('remark', '备注'),
    ]

    return render_template(
        'index.html',
        cameras=cameras,
        pagination=pagination,
        search=search,
        all_columns=all_columns,
        selected_columns=selected_columns,
    )


# ─── 添加相机 ────────────────────────────────────────
@app.route('/add', methods=['GET', 'POST'])
def add():
    """添加相机（支持单个和批量添加）"""
    if request.method == 'POST':
        mode = request.form.get('mode', 'single')

        if mode == 'single':
            return _add_single(request.form)

        if mode == 'batch':
            return _add_batch(request.form)

    return render_template('add.html')


def _add_single(form):
    """处理单个添加"""
    code = form.get('code', '').strip()

    if not code:
        flash('相机编码为必填项', 'danger')
        return redirect(url_for('add'))

    # 唯一性校验
    if Camera.query.filter_by(code=code).first():
        flash(f'相机编码 {code} 已存在，请勿重复添加', 'danger')
        return redirect(url_for('add'))

    camera = _build_camera_from_form(form)
    db.session.add(camera)
    db.session.commit()

    logger.info(f'添加相机: {code}')
    flash(f'相机 {code} 添加成功', 'success')
    return redirect(url_for('index'))


def _add_batch(form):
    """处理批量添加"""
    start_code = form.get('start_code', '').strip()
    end_code = form.get('end_code', '').strip()

    if not start_code or not end_code:
        flash('批量添加需要填写起始编码和结束编码', 'danger')
        return redirect(url_for('add'))

    codes = parse_batch_codes(start_code, end_code)
    if not codes:
        flash('无法解析编码范围，请检查格式（如 09-157-01 到 09-157-10）', 'danger')
        return redirect(url_for('add'))

    added_count = 0
    skipped_codes = []

    for code in codes:
        if Camera.query.filter_by(code=code).first():
            skipped_codes.append(code)
            continue

        camera = _build_camera_from_form(form, code=code)
        db.session.add(camera)
        added_count += 1

    db.session.commit()

    msg = f'成功添加 {added_count} 条记录'
    if skipped_codes:
        msg += f'，跳过 {len(skipped_codes)} 条已存在的编码'
    flash(msg, 'success')
    logger.info(f'批量添加: {added_count} 条，跳过 {len(skipped_codes)} 条')
    return redirect(url_for('index'))


def _build_camera_from_form(form, code=None):
    """从表单数据构建 Camera 对象"""
    lon = format_coordinate(form.get('longitude', '').strip())
    lat = format_coordinate(form.get('latitude', '').strip())

    update_date_str = form.get('update_date', '').strip()
    try:
        update_date = date.fromisoformat(update_date_str)
    except (ValueError, TypeError):
        update_date = date.today()

    return Camera(
        code=code or form.get('code', '').strip(),
        name_751_2024=form.get('name_751_2024', '').strip(),
        name_751_2008=form.get('name_751_2008', '').strip(),
        camera_type=form.get('camera_type', '').strip(),
        longitude=lon,
        latitude=lat,
        location=form.get('location', '').strip(),
        district=form.get('district', '').strip(),
        ip_address=form.get('ip_address', '').strip(),
        operator=form.get('operator', '').strip(),
        maintenance_unit=form.get('maintenance_unit', '').strip(),
        maintenance_person=form.get('maintenance_person', '').strip(),
        maintenance_phone=form.get('maintenance_phone', '').strip(),
        unit_manager=form.get('unit_manager', '').strip(),
        manager_phone=form.get('manager_phone', '').strip(),
        update_date=update_date,
        remark=form.get('remark', '').strip(),
    )


# ─── 编辑相机 ────────────────────────────────────────
@app.route('/edit/<int:camera_id>', methods=['GET', 'POST'])
def edit(camera_id):
    """编辑相机信息"""
    camera = Camera.query.get_or_404(camera_id)

    if request.method == 'POST':
        code = request.form.get('code', '').strip()

        # 编码唯一性校验（排除自身）
        existing = Camera.query.filter(
            Camera.code == code,
            Camera.id != camera_id
        ).first()
        if existing:
            flash(f'相机编码 {code} 已被其他记录使用', 'danger')
            return render_template('edit.html', camera=camera)

        camera.code = code
        camera.name_751_2024 = request.form.get('name_751_2024', '').strip()
        camera.name_751_2008 = request.form.get('name_751_2008', '').strip()
        camera.camera_type = request.form.get('camera_type', '').strip()
        camera.longitude = format_coordinate(request.form.get('longitude', '').strip())
        camera.latitude = format_coordinate(request.form.get('latitude', '').strip())
        camera.location = request.form.get('location', '').strip()
        camera.district = request.form.get('district', '').strip()
        camera.ip_address = request.form.get('ip_address', '').strip()
        camera.operator = request.form.get('operator', '').strip()
        camera.maintenance_unit = request.form.get('maintenance_unit', '').strip()
        camera.maintenance_person = request.form.get('maintenance_person', '').strip()
        camera.maintenance_phone = request.form.get('maintenance_phone', '').strip()
        camera.unit_manager = request.form.get('unit_manager', '').strip()
        camera.manager_phone = request.form.get('manager_phone', '').strip()

        update_date_str = request.form.get('update_date', '').strip()
        try:
            camera.update_date = date.fromisoformat(update_date_str)
        except (ValueError, TypeError):
            camera.update_date = date.today()

        camera.remark = request.form.get('remark', '').strip()

        db.session.commit()
        logger.info(f'更新相机: {camera.code}')
        flash('相机信息更新成功', 'success')
        return redirect(url_for('index'))

    return render_template('edit.html', camera=camera)


# ─── 删除相机 ────────────────────────────────────────
@app.route('/delete/<int:camera_id>', methods=['POST'])
def delete(camera_id):
    """删除单个相机"""
    camera = Camera.query.get_or_404(camera_id)
    code = camera.code
    db.session.delete(camera)
    db.session.commit()
    logger.info(f'删除相机: {code}')
    flash(f'相机 {code} 已删除', 'success')
    return redirect(url_for('index'))


@app.route('/batch-delete', methods=['POST'])
def batch_delete():
    """批量删除"""
    ids = request.form.getlist('ids')
    if not ids:
        flash('请选择要删除的记录', 'warning')
        return redirect(url_for('index'))

    count = Camera.query.filter(Camera.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    logger.info(f'批量删除: {count} 条')
    flash(f'成功删除 {count} 条记录', 'success')
    return redirect(url_for('index'))


# ─── 查看详情 ────────────────────────────────────────
@app.route('/detail/<int:camera_id>')
def detail(camera_id):
    """查看相机详细信息（返回 JSON）"""
    camera = Camera.query.get_or_404(camera_id)
    return jsonify(camera.to_dict())


# ─── 自动补全 ────────────────────────────────────────
@app.route('/autocomplete')
def autocomplete():
    """返回常用字段的已有值列表，用于前端自动补全"""
    field = request.args.get('field', '')
    allowed_fields = [
        'district', 'maintenance_unit', 'maintenance_person',
        'operator', 'camera_type', 'location'
    ]
    if field not in allowed_fields:
        return jsonify([])

    values = (
        db.session.query(getattr(Camera, field))
        .filter(getattr(Camera, field) != '')
        .distinct()
        .order_by(getattr(Camera, field))
        .all()
    )
    return jsonify([v[0] for v in values])


# ─── Excel 导出 ──────────────────────────────────────
@app.route('/export')
def export_excel():
    """导出相机列表为 Excel"""
    search = request.args.get('search', '').strip()

    query = Camera.query
    if search:
        query = query.filter(
            db.or_(
                Camera.ip_address.contains(search),
                Camera.name_751_2024.contains(search),
                Camera.code.contains(search),
                Camera.maintenance_unit.contains(search),
                Camera.maintenance_person.contains(search),
                Camera.district.contains(search),
            )
        )
    query = query.order_by(Camera.code)
    cameras = query.all()

    wb = Workbook()
    ws = wb.active
    ws.title = '相机列表'

    # 表头
    headers = [
        '相机编码', '相机名称（751-2024）', '相机名称（751-2008）', '相机类型',
        'IP地址', '经度', '纬度', '地理位置', '所属辖区',
        '运营商', '运维单位', '运维人员', '运维人员电话',
        '运维单位责任人', '单位责任人电话', '更新日期', '备注'
    ]
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True, size=11)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border

    # 数据行
    for row_idx, cam in enumerate(cameras, 2):
        values = [
            cam.code, cam.name_751_2024, cam.name_751_2008, cam.camera_type,
            cam.ip_address, cam.longitude, cam.latitude, cam.location, cam.district,
            cam.operator, cam.maintenance_unit, cam.maintenance_person,
            cam.maintenance_phone, cam.unit_manager, cam.manager_phone,
            str(cam.update_date) if cam.update_date else '', cam.remark
        ]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = thin_border
            cell.alignment = Alignment(vertical='center')

    # 调整列宽
    col_widths = [16, 22, 22, 10, 15, 12, 12, 20, 14, 12, 16, 12, 15, 14, 15, 12, 20]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'相机列表_{date.today().isoformat()}.xlsx'
    )


# ─── Excel 导入 ──────────────────────────────────────
@app.route('/import', methods=['POST'])
def import_excel():
    """从 Excel 导入相机数据"""
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('请选择要导入的 Excel 文件', 'warning')
        return redirect(url_for('index'))

    try:
        wb = load_workbook(file, read_only=True)
        ws = wb.active
    except Exception as e:
        flash(f'无法读取 Excel 文件：{e}', 'danger')
        return redirect(url_for('index'))

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        flash('Excel 文件没有数据行', 'warning')
        return redirect(url_for('index'))

    # 映射：表头列名 → 数据库字段
    header_map = {
        '相机编码': 'code',
        '相机名称（751-2024）': 'name_751_2024',
        '相机名称（751-2008）': 'name_751_2008',
        '相机类型': 'camera_type',
        'IP地址': 'ip_address',
        '经度': 'longitude',
        '纬度': 'latitude',
        '地理位置': 'location',
        '所属辖区': 'district',
        '运营商': 'operator',
        '运维单位': 'maintenance_unit',
        '运维人员': 'maintenance_person',
        '运维人员电话': 'maintenance_phone',
        '运维单位责任人': 'unit_manager',
        '单位责任人电话': 'manager_phone',
        '更新日期': 'update_date',
        '备注': 'remark',
    }

    headers = [str(h).strip() if h else '' for h in rows[0]]
    col_index = {}
    for idx, h in enumerate(headers):
        if h in header_map:
            col_index[idx] = header_map[h]

    if 'code' not in col_index.values():
        flash('Excel 文件中缺少"相机编码"列', 'danger')
        return redirect(url_for('index'))

    added_count = 0
    updated_count = 0
    error_rows = []

    for row_idx, row in enumerate(rows[1:], 2):
        data = {}
        for col_idx, field in col_index.items():
            val = row[col_idx] if col_idx < len(row) else None
            data[field] = str(val).strip() if val is not None else ''

        code = data.get('code', '')
        if not code:
            error_rows.append(f'第{row_idx}行：编码为空')
            continue

        # 处理经纬度
        data['longitude'] = format_coordinate(data.get('longitude', ''))
        data['latitude'] = format_coordinate(data.get('latitude', ''))

        # 处理日期
        update_date_str = data.get('update_date', '')
        try:
            data['update_date'] = date.fromisoformat(update_date_str) if update_date_str else date.today()
        except (ValueError, TypeError):
            data['update_date'] = date.today()

        existing = Camera.query.filter_by(code=code).first()
        if existing:
            # 更新已有记录
            for field, value in data.items():
                if field != 'code':
                    setattr(existing, field, value)
            updated_count += 1
        else:
            # 新增
            camera = Camera(**data)
            db.session.add(camera)
            added_count += 1

    db.session.commit()
    msg = f'导入完成：新增 {added_count} 条，更新 {updated_count} 条'
    if error_rows:
        msg += f'，{len(error_rows)} 行出错'
        logger.warning(f'导入错误行: {error_rows}')
    flash(msg, 'success')
    logger.info(msg)
    return redirect(url_for('index'))


# ─── 应用启动 ────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)