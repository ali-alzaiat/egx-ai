/**
 * Debounce a function so it only executes after `delay` milliseconds of
 * non-invocation. Returns a throttled function.
 */
export function debounce<T extends (...args: never[]) => void>(
  fn: T,
  delay: number
): T {
  let timeoutId: ReturnType<typeof window.setTimeout>
  return ((...args: Parameters<T>) => {
    window.clearTimeout(timeoutId)
    timeoutId = window.setTimeout(() => fn(...args), delay)
  }) as T
}