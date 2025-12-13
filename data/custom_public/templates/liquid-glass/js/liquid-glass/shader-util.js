// Adapted from https://github.com/shuding/liquid-glass

const fragmentShaders = {
  liquidGlass: 'liquidGlass',
  liquidGlass2: 'liquidGlass2',
  flowingLiquid: 'flowingLiquid',
  transparentIce: 'transparentIce',
  unevenGlass: 'unevenGlass',
  mosaicGlass: 'mosaicGlass',
}

class ShaderDisplacementGenerator {
  constructor(options) {
    this.options = options
    this.startTime = Date.now()
    // 使用相对路径加载 worker
    this.worker = new Worker('./js/liquid-glass/workers/shader-worker.js')
  }

  updateShader(mousePosition) {
    const currentTime = (Date.now() - this.startTime) / 1000 // Time in seconds

    return new Promise((resolve) => {
      this.worker.onmessage = (e) => {
        const { imageData } = e.data
        const canvas = document.createElement('canvas')
        canvas.width = this.options.width
        canvas.height = this.options.height
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.putImageData(imageData, 0, 0)
          resolve(canvas.toDataURL())
        }
      }

      this.worker.postMessage({
        width: this.options.width,
        height: this.options.height,
        effect: this.options.effect,
        mousePosition,
        time: currentTime,
      })
    })
  }

  destroy() {
    this.worker.terminate()
  }

  getCurrentTime() {
    return (Date.now() - this.startTime) / 1000
  }
}

// 挂载到全局对象
(function() {
  if (typeof window !== 'undefined') {
    window.ShaderDisplacementGenerator = ShaderDisplacementGenerator
    window.fragmentShaders = fragmentShaders
  }
})()

