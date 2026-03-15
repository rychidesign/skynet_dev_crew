export function getScoreColor(score: number): { text: string; bg: string; stroke: string } {
  if (score < 25) {
    return { text: 'text-red-500', bg: 'bg-red-50', stroke: 'stroke-red-500' };
  }
  if (score < 50) {
    return { text: 'text-orange-500', bg: 'bg-orange-50', stroke: 'stroke-orange-500' };
  }
  if (score < 75) {
    return { text: 'text-yellow-600', bg: 'bg-yellow-50', stroke: 'stroke-yellow-500' };
  }
  if (score < 90) {
    return { text: 'text-blue-600', bg: 'bg-blue-50', stroke: 'stroke-blue-500' };
  }
  return { text: 'text-green-600', bg: 'bg-green-50', stroke: 'stroke-green-500' };
}

export function getRatingLabel(score: number): string {
  if (score < 25) return 'critical';
  if (score < 50) return 'weak';
  if (score < 75) return 'moderate';
  if (score < 90) return 'strong';
  return 'excellent';
}
