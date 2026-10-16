import { redirectHeadlessConsole } from './headless-console.ts'

const originalError = console.error
redirectHeadlessConsole()
if (console.error !== originalError) {
  process.stderr.write('console.error replaced\n')
  process.exit(2)
}

const { CLog } = await import('../utils/logUtil.ts')
CLog.debug('CLOG_DEBUG_MARKER')
process.stdout.write('STDOUT_OK\n')
