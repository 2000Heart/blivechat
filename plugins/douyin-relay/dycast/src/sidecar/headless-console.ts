/** Point debug, info, and warn at stderr. Leave console.error unchanged. */
export function redirectHeadlessConsole(): void {
  const writeLog = console.error.bind(console)
  console.log = writeLog
  console.info = writeLog
  console.debug = writeLog
  console.warn = writeLog
}
