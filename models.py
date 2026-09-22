"""
相机地址管理系统 - 数据库模型
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()


class Camera(db.Model):
    """相机型号"""
    __tablename__ = 'cameras'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    camera_type = db.Column(db.String(20), default='')          # 相机类型
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)  # 相机编码（唯一）
    name_751_2024 = db.Column(db.String(200), default='')       # 相机名称（751-2024）
    name_751_2008 = db.Column(db.String(200), default='')       # 相机名称（751-2008）
    longitude = db.Column(db.String(20), default='')            # 经度（6位小数）
    latitude = db.Column(db.String(20), default='')             # 纬度（6位小数）
    location = db.Column(db.String(300), default='')            # 地理位置
    district = db.Column(db.String(100), default='')            # 所属辖区
    ip_address = db.Column(db.String(50), default='')           # IP地址
    operator = db.Column(db.String(50), default='')             # 运营商
    maintenance_unit = db.Column(db.String(100), default='')    # 运维单位
    maintenance_person = db.Column(db.String(50), default='')   # 运维人员
    maintenance_phone = db.Column(db.String(20), default='')    # 运维人员电话
    unit_manager = db.Column(db.String(50), default='')         # 运维单位责任人
    manager_phone = db.Column(db.String(20), default='')        # 单位责任人电话
    update_date = db.Column(db.Date, default=date.today)        # 更新日期
    remark = db.Column(db.Text, default='')                     # 备注

    def to_dict(self):
        """转为字典"""
        return {
            'id': self.id,
            'camera_type': self.camera_type,
            'code': self.code,
            'name_751_2024': self.name_751_2024,
            'name_751_2008': self.name_751_2008,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'location': self.location,
            'district': self.district,
            'ip_address': self.ip_address,
            'operator': self.operator,
            'maintenance_unit': self.maintenance_unit,
            'maintenance_person': self.maintenance_person,
            'maintenance_phone': self.maintenance_phone,
            'unit_manager': self.unit_manager,
            'manager_phone': self.manager_phone,
            'update_date': str(self.update_date) if self.update_date else '',
            'remark': self.remark,
        }

    def __repr__(self):
        return f'<Camera {self.code} - {self.name_751_2024}>'