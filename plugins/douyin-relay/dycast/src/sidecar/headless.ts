import { redirectHeadlessConsole } from './headless-console.ts'

// logUtil.ts captures console.log when it loads. Patch before that import graph.
redirectHeadlessConsole()

await import('./headless-main.ts')
