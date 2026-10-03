export function getArabicGreeting(date = new Date()): string {
  const hour = date.getHours();
  if (hour < 5) return "مساء الخير";
  if (hour < 12) return "صباح الخير";
  if (hour < 17) return "نهارك سعيد";
  if (hour < 20) return "مساء الخير";
  return "مساء الخير";
}
