#!/usr/bin/env python3
"""
种子数据脚本 — 人教版初中数学知识点图谱

用法: python scripts/seed_learning_data.py

入库顺序:
  1. learning_subjects (数学)
  2. learning_textbook_versions (人教版 × 6册)
  3. learning_knowledge_points (50个核心知识点 + 父子关系 + 前置依赖)
"""
import asyncio
import json
import sys
import os
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import get_settings
from infrastructure.database.models import (
    LearningSubject,
    LearningTextbookVersion,
    LearningKnowledgePoint,
    LearningErrorRecord,
)
from databases import Database
from sqlalchemy import select


# ============================================================
# 数学学科数据 (人教版初中 7-9年级)
# ============================================================

TEXTBOOK_VERSIONS = [
    # (publisher, grade, semester, is_default)
    ("人教版", 7, 1, True),
    ("人教版", 7, 2, False),
    ("人教版", 8, 1, False),
    ("人教版", 8, 2, False),
    ("人教版", 9, 1, False),
    ("人教版", 9, 2, False),
]

# 知识点定义: (code, name, grade, semester, chapter, page_range, difficulty, parent_idx, prerequisite_codes)
# parent_idx = None → 根节点; 数字 = 子节点在列表中的序号(0-based)
# prerequisite_codes = 前置知识点code列表 (必须先掌握这些才能学本知识点)
KNOWLEDGE_POINTS = [
    # ====== 七年级上 (7A) ======
    ("M7-C1-KP01", "有理数的概念与分类", 7, 1, "第1章 有理数", "P2-P14", 1, None, []),
    ("M7-C1-KP02", "有理数的四则运算", 7, 1, "第1章 有理数", "P15-P35", 2, None, ["M7-C1-KP01"]),
    ("M7-C1-KP03", "乘方与科学记数法", 7, 1, "第1章 有理数", "P36-P47", 2, None, ["M7-C1-KP02"]),
    ("M7-C2-KP01", "整式的概念与加减运算", 7, 1, "第2章 整式的加减", "P53-P71", 2, None, []),
    ("M7-C3-KP01", "等式的性质", 7, 1, "第3章 一元一次方程", "P78-P84", 2, None, ["M7-C1-KP02"]),
    ("M7-C3-KP02", "一元一次方程的解法", 7, 1, "第3章 一元一次方程", "P85-P95", 3, None, ["M7-C3-KP01"]),
    ("M7-C3-KP03", "移项法则", 7, 1, "第3章 一元一次方程", "P85-P88", 2, 5, ["M7-C3-KP01"]),  # child of KP02
    ("M7-C3-KP04", "一元一次方程的应用", 7, 1, "第3章 一元一次方程", "P96-P112", 4, None, ["M7-C3-KP02"]),
    ("M7-C4-KP01", "线段、射线与直线", 7, 1, "第4章 几何图形初步", "P118-P126", 1, None, []),
    ("M7-C4-KP02", "角的概念与度量", 7, 1, "第4章 几何图形初步", "P127-P136", 2, None, []),
    ("M7-C4-KP03", "余角与补角", 7, 1, "第4章 几何图形初步", "P137-P142", 2, 9, []),  # child of KP02

    # ====== 七年级下 (7B) ======
    ("M7-C5-KP01", "相交线与对顶角", 7, 2, "第5章 相交线与平行线", "P2-P12", 2, None, ["M7-C4-KP02"]),
    ("M7-C5-KP02", "平行线的判定与性质", 7, 2, "第5章 相交线与平行线", "P13-P30", 3, None, ["M7-C5-KP01"]),
    ("M7-C6-KP01", "平方根与立方根", 7, 2, "第6章 实数", "P38-P50", 3, None, ["M7-C1-KP02"]),
    ("M7-C6-KP02", "实数的概念与运算", 7, 2, "第6章 实数", "P51-P62", 3, None, ["M7-C6-KP01"]),
    ("M7-C7-KP01", "平面直角坐标系", 7, 2, "第7章 平面直角坐标系", "P72-P88", 2, None, []),
    ("M7-C8-KP01", "二元一次方程组的概念", 7, 2, "第8章 二元一次方程组", "P95-P100", 2, None, ["M7-C3-KP02"]),
    ("M7-C8-KP02", "代入消元法与加减消元法", 7, 2, "第8章 二元一次方程组", "P101-P112", 3, None, ["M7-C8-KP01"]),
    ("M7-C8-KP03", "二元一次方程组的应用", 7, 2, "第8章 二元一次方程组", "P113-P126", 4, None, ["M7-C8-KP02"]),
    ("M7-C9-KP01", "不等式及其解集", 7, 2, "第9章 不等式与不等式组", "P133-P142", 2, None, ["M7-C3-KP02"]),
    ("M7-C9-KP02", "一元一次不等式的解法", 7, 2, "第9章 不等式与不等式组", "P143-P155", 3, None, ["M7-C9-KP01"]),
    ("M7-C9-KP03", "一元一次不等式组的应用", 7, 2, "第9章 不等式与不等式组", "P156-P168", 4, None, ["M7-C9-KP02"]),

    # ====== 八年级上 (8A) ======
    ("M8-C11-KP01", "三角形的边与角", 8, 1, "第11章 三角形", "P2-P16", 2, None, ["M7-C4-KP02"]),
    ("M8-C11-KP02", "三角形全等的判定(SSS/SAS/ASA/AAS)", 8, 1, "第11章 三角形", "P17-P42", 4, None, ["M8-C11-KP01"]),
    ("M8-C11-KP03", "直角三角形全等的判定(HL)", 8, 1, "第11章 三角形", "P43-P48", 4, None, ["M8-C11-KP02"]),
    ("M8-C12-KP01", "轴对称与垂直平分线", 8, 1, "第12章 轴对称", "P56-P72", 3, None, ["M8-C11-KP01"]),
    ("M8-C12-KP02", "等腰三角形与等边三角形", 8, 1, "第12章 轴对称", "P73-P86", 3, None, ["M8-C11-KP02", "M8-C12-KP01"]),
    ("M8-C13-KP01", "幂的运算法则", 8, 1, "第13章 整式的乘法", "P92-P98", 2, None, ["M7-C1-KP03"]),
    ("M8-C13-KP02", "整式的乘法与因式分解", 8, 1, "第13章 整式的乘除与因式分解", "P99-P126", 4, None, ["M8-C13-KP01", "M7-C2-KP01"]),
    ("M8-C13-KP03", "提公因式法", 8, 1, "第13章 整式的乘除与因式分解", "P113-P117", 2, 29, ["M8-C13-KP02"]),
    ("M8-C13-KP04", "公式法（平方差/完全平方）", 8, 1, "第13章 整式的乘除与因式分解", "P118-P126", 3, 29, ["M8-C13-KP02"]),
    ("M8-C13-KP05", "分式的概念与运算", 8, 1, "第14章 分式", "P132-P152", 3, None, ["M8-C13-KP02"]),
    ("M8-C13-KP06", "分式方程的解法与应用", 8, 1, "第14章 分式", "P153-P170", 4, None, ["M8-C13-KP05", "M7-C3-KP02"]),

    # ====== 八年级下 (8B) ======
    ("M8-C16-KP01", "二次根式的化简与运算", 8, 2, "第16章 二次根式", "P2-P20", 3, None, ["M7-C6-KP02"]),
    ("M8-C17-KP01", "勾股定理及其逆定理", 8, 2, "第17章 勾股定理", "P28-P50", 4, None, ["M7-C6-KP02", "M8-C11-KP01"]),
    ("M8-C18-KP01", "平行四边形的性质与判定", 8, 2, "第18章 平行四边形", "P56-P82", 3, None, ["M7-C5-KP02", "M8-C11-KP01"]),
    ("M8-C18-KP02", "矩形与菱形的性质与判定", 8, 2, "第18章 平行四边形", "P83-P104", 4, None, ["M8-C18-KP01"]),
    ("M8-C18-KP03", "正方形的性质与判定", 8, 2, "第18章 平行四边形", "P105-P112", 4, None, ["M8-C18-KP02"]),
    ("M8-C19-KP01", "正比例函数", 8, 2, "第19章 一次函数", "P120-P126", 2, None, ["M7-C7-KP01"]),
    ("M8-C19-KP02", "一次函数的图像与性质", 8, 2, "第19章 一次函数", "P127-P144", 3, None, ["M8-C19-KP01"]),
    ("M8-C19-KP03", "一次函数与方程/不等式的联系", 8, 2, "第19章 一次函数", "P145-P160", 4, None, ["M8-C19-KP02", "M7-C8-KP02"]),
    ("M8-C20-KP01", "平均数/中位数/众数", 8, 2, "第20章 数据的分析", "P168-P182", 2, None, []),
    ("M8-C20-KP02", "方差与标准差", 8, 2, "第20章 数据的分析", "P183-P196", 3, None, ["M8-C20-KP01"]),

    # ====== 九年级上 (9A) ======
    ("M9-C21-KP01", "一元二次方程的概念", 9, 1, "第21章 一元二次方程", "P2-P8", 2, None, ["M8-C13-KP02"]),
    ("M9-C21-KP02", "配方法与公式法解一元二次方程", 9, 1, "第21章 一元二次方程", "P9-P28", 3, None, ["M9-C21-KP01", "M8-C13-KP04"]),
    ("M9-C21-KP03", "因式分解法解一元二次方程", 9, 1, "第21章 一元二次方程", "P29-P36", 3, None, ["M9-C21-KP01", "M8-C13-KP02"]),
    ("M9-C21-KP04", "判别式与韦达定理", 9, 1, "第21章 一元二次方程", "P37-P48", 4, None, ["M9-C21-KP02"]),
    ("M9-C21-KP05", "一元二次方程的应用", 9, 1, "第21章 一元二次方程", "P49-P58", 4, None, ["M9-C21-KP02", "M9-C21-KP03"]),
    ("M9-C22-KP01", "二次函数的图像与性质", 9, 1, "第22章 二次函数", "P66-P88", 4, None, ["M8-C19-KP02", "M9-C21-KP02"]),
    ("M9-C22-KP02", "二次函数的平移与顶点式", 9, 1, "第22章 二次函数", "P89-P100", 4, None, ["M9-C22-KP01"]),
    ("M9-C22-KP03", "二次函数与实际应用", 9, 1, "第22章 二次函数", "P101-P118", 5, None, ["M9-C22-KP02"]),
    ("M9-C23-KP01", "旋转的性质与作图", 9, 1, "第23章 旋转", "P125-P140", 3, None, ["M8-C12-KP01"]),
    ("M9-C24-KP01", "垂径定理与圆周角定理", 9, 1, "第24章 圆", "P148-P176", 4, None, ["M8-C11-KP01"]),
    ("M9-C24-KP02", "切线性质与判定", 9, 1, "第24章 圆", "P177-P198", 5, None, ["M9-C24-KP01"]),

    # ====== 九年级下 (9B) ======
    ("M9-C25-KP01", "相似三角形的判定与性质", 9, 2, "第25章 相似", "P2-P30", 4, None, ["M8-C11-KP02"]),
    ("M9-C25-KP02", "相似三角形在实际中的应用", 9, 2, "第25章 相似", "P31-P42", 4, None, ["M9-C25-KP01", "M8-C17-KP01"]),
    ("M9-C26-KP01", "锐角三角函数(sin/cos/tan)", 9, 2, "第26章 锐角三角函数", "P50-P68", 4, None, ["M8-C17-KP01", "M8-C13-KP05"]),
    ("M9-C26-KP02", "解直角三角形及其应用", 9, 2, "第26章 锐角三角函数", "P69-P88", 5, None, ["M9-C26-KP01"]),
]

# 常见错误类型预设 (供 Stage3 历史案例匹配)
COMMON_ERRORS = [
    ("计算错误", "数字运算失误，如符号弄反、加减乘除错误"),
    ("概念不清", "对知识点概念理解不透彻，导致用错公式或定理"),
    ("审题失误", "遗漏题目关键条件或误解题意"),
    ("公式记错", "记忆错误公式或混淆相似公式"),
    ("步骤遗漏", "解题步骤不完整，跳步或省略必要推理"),
    ("单位/格式错误", "忘记写单位、答句格式不规范"),
    ("逻辑错误", "推理链条中断，因果关系不成立"),
]


async def seed(settings):
    db = Database(settings.database.url)
    await db.connect()

    try:
        # ——— 1. Subject ———
        sub_id = str(uuid4())
        await db.execute(
            "INSERT INTO learning_subjects (id, name, grade_level, sort_order, created_at) "
            "VALUES (:id, :name, :grade, :sort, NOW())",
            {"id": sub_id, "name": "数学", "grade": "junior_high", "sort": 1}
        )
        print(f"✓ 学科: 数学 (id={sub_id})")

        # ——— 2. Textbook Versions ———
        tv_ids = {}  # (grade, semester) → id
        for publisher, grade, semester, is_default in TEXTBOOK_VERSIONS:
            tid = str(uuid4())
            tv_ids[(grade, semester)] = tid
            await db.execute(
                "INSERT INTO learning_textbook_versions (id, subject_id, publisher, grade, semester, is_default, created_at) "
                "VALUES (:id, :sid, :pub, :g, :sem, :def, NOW())",
                {"id": tid, "sid": sub_id, "pub": publisher, "g": grade, "sem": semester, "def": is_default}
            )
        print(f"✓ 教材版本: {len(TEXTBOOK_VERSIONS)} 册 (人教版 7A-9B)")

        # ——— 3. Knowledge Points ———
        kp_map = {}  # code → id (用于解析前置依赖和父子关系)
        created_count = 0

        for (code, name, grade, semester, chapter, page_range, difficulty, parent_code_idx, prerequisites) in KNOWLEDGE_POINTS:
            kp_id = str(uuid4())
            kp_map[code] = kp_id
            tv_id = tv_ids.get((grade, semester))

            # 前置知识点暂时存 code，后续再更新为 id
            await db.execute(
                """INSERT INTO learning_knowledge_points
                   (id, subject_id, textbook_version_id, name, code, chapter, page_range,
                    difficulty_level, prerequisite_kp_ids, sort_order, metadata, created_at)
                   VALUES (:id, :sid, :tvid, :name, :code, :ch, :pr, :diff, :preq, :sort, :meta, NOW())""",
                {
                    "id": kp_id,
                    "sid": sub_id,
                    "tvid": tv_id,
                    "name": name,
                    "code": code,
                    "ch": chapter,
                    "pr": page_range,
                    "diff": difficulty,
                    "preq": json.dumps(prerequisites),  # 存 code 列表，后续由 post_seed 转为 id 列表
                    "sort": created_count,
                    "meta": json.dumps({}),
                }
            )
            created_count += 1

        print(f"✓ 知识点: {created_count} 个")

        # ——— 4. 解析父子关系和前置依赖为 UUID ———
        for (code, name, grade, semester, chapter, page_range, difficulty, parent_code_idx, prerequisites) in KNOWLEDGE_POINTS:
            kp_id = kp_map[code]

            # 设置 parent_id
            if parent_code_idx is not None and parent_code_idx < len(KNOWLEDGE_POINTS):
                parent_code = KNOWLEDGE_POINTS[parent_code_idx][0]
                parent_id = kp_map.get(parent_code)
                if parent_id and parent_id != kp_id:
                    await db.execute(
                        "UPDATE learning_knowledge_points SET parent_id = :pid WHERE id = :id",
                        {"pid": parent_id, "id": kp_id}
                    )

            # 将 prerequisite_codes 转换为 prerequisite_kp_ids (UUID列表)
            if prerequisites:
                prereq_ids = [kp_map[p] for p in prerequisites if p in kp_map]
                if prereq_ids:
                    await db.execute(
                        "UPDATE learning_knowledge_points SET prerequisite_kp_ids = :preq WHERE id = :id",
                        {"preq": json.dumps(prereq_ids), "id": kp_id}
                    )

        # ——— 5. 常见错误类型入库 ———
        error_count = 0
        for etype, edesc in COMMON_ERRORS:
            # 为每个错误类型关联一个通用的知识点 (第一个知识点)
            first_kp_id = list(kp_map.values())[0]
            await db.execute(
                "INSERT INTO learning_error_records (id, knowledge_point_id, error_type, error_description, frequency, created_at) "
                "VALUES (:id, :kpid, :etype, :edesc, 1, NOW())",
                {"id": str(uuid4()), "kpid": first_kp_id, "etype": etype, "edesc": edesc}
            )
            error_count += 1
        print(f"✓ 常见错误类型: {error_count} 种")

        # ——— 6. 统计输出 ———
        result = await db.fetch_one("SELECT COUNT(*) FROM learning_knowledge_points")
        total_kp = result[0] if result else 0

        print(f"\n{'='*50}")
        print(f"种子数据导入完成!")
        print(f"  学科: 1 (数学-初中)")
        print(f"  教材版本: 6 册 (人教版 7A-9B)")
        print(f"  知识点: {total_kp} 个 (含父子关系 + 前置依赖)")
        print(f"  错误类型: {error_count} 种")
        print(f"{'='*50}")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    settings = get_settings()
    asyncio.run(seed(settings))
