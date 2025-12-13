// Type definitions for Liquid Glass components

const GlassMode = {
  standard: 'standard',
  polar: 'polar',
  prominent: 'prominent',
  shader: 'shader',
}

// Export to global scope
if (typeof window !== 'undefined') {
  window.GlassMode = GlassMode
}

