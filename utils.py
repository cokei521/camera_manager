"""
相机地址管理系统 - 工具函数
"""
import re


def format_coordinate(value):
    """
    格式化经纬度，保留小数点后6位。
    例如: "118.794058" → "118.794058"
    """
    if not value:
        return ''
    try:
        return f'{float(value):.6f}'
    except (ValueError, TypeError):
        return value


def parse_batch_codes(start_code, end_code):
    """
    解析批量编码范围。

    支持的格式：
      - 同段递增：09-157-01 → 09-157-10
      - 跨段：09-157-99 → 09-158-05

    返回编码列表。
    """
    if not start_code or not end_code:
        return []

    # 尝试匹配 "XX-XXX-XX" 格式
    pattern = r'^(\d+)-(\d+)-(\d+)$'
    m_start = re.match(pattern, start_code.strip())
    m_end = re.match(pattern, end_code.strip())

    if not m_start or not m_end:
        return []

    part1_start, part2_start, part3_start = int(m_start.group(1)), int(m_start.group(2)), int(m_start.group(3))
    part1_end, part2_end, part3_end = int(m_end.group(1)), int(m_end.group(2)), int(m_end.group(3))

    # 确保起始 ≤ 结束
    start_val = part1_start * 100000 + part2_start * 100 + part3_start
    end_val = part1_end * 100000 + part2_end * 100 + part3_end

    if start_val > end_val:
        return []

    codes = []
    current = start_val
    while current <= end_val:
        p1 = current // 100000
        p2 = (current % 100000) // 100
        p3 = current % 100
        codes.append(f'{p1:02d}-{p2:03d}-{p3:02d}')
        current += 1

    return codes


def natural_sort_key(s):
    """
    自然排序键函数，用于 SQLite 的排序。
    将字符串中的数字转为整数后排序，如：
      '09-157-01' < '09-157-02' < '09-157-10'
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]