interface GradeRow {
  score: number;
  exam: { date: string; total_score: number } | null;
}

export function buildStudentInsights({
  grades,
  attendanceRate,
  homeworkCompletionRate,
}: {
  grades: GradeRow[];
  attendanceRate: number | null;
  homeworkCompletionRate: number | null;
}): string[] {
  const insights: string[] = [];

  const sorted = [...grades]
    .filter((g) => g.exam)
    .sort((a, b) => new Date(b.exam!.date).getTime() - new Date(a.exam!.date).getTime());

  if (sorted.length >= 2) {
    const recentPct = (sorted[0].score / (sorted[0].exam!.total_score || 1)) * 100;
    const prevPct = (sorted[1].score / (sorted[1].exam!.total_score || 1)) * 100;
    const diff = Math.round(recentPct - prevPct);
    if (diff <= -10) {
      insights.push(`انخفض أداء الطالب بنسبة ${Math.abs(diff)}٪ مقارنة بالاختبار السابق، وقد يحتاج إلى متابعة إضافية.`);
    } else if (diff >= 10) {
      insights.push(`تحسّن أداء الطالب بنسبة ${diff}٪ مقارنة بالاختبار السابق.`);
    } else {
      insights.push("أداء الطالب مستقر نسبياً مقارنة بالاختبار السابق.");
    }
  } else if (sorted.length === 1) {
    insights.push("يوجد اختبار واحد فقط مسجل حتى الآن، ولا يمكن تحديد الاتجاه بعد.");
  }

  if (attendanceRate !== null) {
    if (attendanceRate < 70) {
      insights.push(`نسبة الحضور منخفضة (${attendanceRate}٪) خلال آخر السجلات، يُنصح بالتواصل مع ولي الأمر.`);
    } else if (attendanceRate >= 90) {
      insights.push(`نسبة الحضور ممتازة (${attendanceRate}٪).`);
    }
  }

  if (homeworkCompletionRate !== null && homeworkCompletionRate < 60) {
    insights.push(`نسبة إنجاز الواجبات منخفضة (${homeworkCompletionRate}٪)، قد يستفيد الطالب من متابعة إضافية في المنزل.`);
  }

  if (insights.length === 0) {
    insights.push("لا توجد بيانات كافية بعد لتوليد تحليل دقيق لهذا الطالب.");
  }

  return insights;
}
