from __future__ import annotations
from storage import empty_workspace


def demo_workspace():
    d = empty_workspace()
    d["students"] = [
        {"student_id": "S001", "display_name": "学生A", "grade": "高一", "school": "示例学校", "target_score": 85, "notes": "示例数据，请替换为匿名学生编号"},
        {"student_id": "S002", "display_name": "学生B", "grade": "高二", "school": "示例学校", "target_score": 90, "notes": "示例数据"},
    ]
    d["exams"] = [
        {"exam_id": "E001", "student_id": "S001", "exam_name": "第一次月考", "date": "2026-08-20", "total_score": 62, "max_score": 100},
        {"exam_id": "E002", "student_id": "S001", "exam_name": "第二次周测", "date": "2026-09-01", "total_score": 68, "max_score": 100},
        {"exam_id": "E003", "student_id": "S001", "exam_name": "第三次周测", "date": "2026-09-12", "total_score": 72, "max_score": 100},
    ]
    rows = [
        ("E001",1,"运动学",3,5,5,"无","基础知识"),("E001",2,"受力分析",3,3,5,"受力分析","受力分析"),("E001",3,"摩擦力临界",4,1,6,"临界判断","临界判断"),("E001",4,"牛顿第二定律",4,4,8,"模型识别","模型识别"),("E001",5,"图像问题",3,5,6,"计算","数学处理"),("E001",6,"板块模型",5,3,10,"模型识别","综合迁移"),
        ("E002",1,"运动学",3,5,5,"无","基础知识"),("E002",2,"受力分析",3,4,5,"受力分析","受力分析"),("E002",3,"摩擦力临界",4,2,6,"临界判断","临界判断"),("E002",4,"牛顿第二定律",4,5,8,"模型识别","模型识别"),("E002",5,"图像问题",3,6,6,"无","数学处理"),("E002",6,"板块模型",5,4,10,"模型识别","综合迁移"),
        ("E003",1,"运动学",3,5,5,"无","基础知识"),("E003",2,"受力分析",3,4,5,"审题","受力分析"),("E003",3,"摩擦力临界",4,3,6,"临界判断","临界判断"),("E003",4,"牛顿第二定律",4,6,8,"模型识别","模型识别"),("E003",5,"图像问题",3,6,6,"无","数学处理"),("E003",6,"板块模型",5,5,10,"综合迁移","综合迁移"),
    ]
    for exam_id, no, topic, diff, score, max_score, err, skill in rows:
        d["questions"].append({"exam_id":exam_id,"student_id":"S001","question_no":no,"topic":topic,"difficulty":diff,"score":score,"max_score":max_score,"error_type":err,"skill":skill})
    return d
