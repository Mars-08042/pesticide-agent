/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          DEFAULT: '#f8f9f8',
          50: '#f8f9f8',
          100: '#f6f8f7',
          200: '#eef2f0',
          300: '#dce5e0',
          dark: '#eef2f0',
        },
        'brand-green': {
          DEFAULT: '#6f9a8a',
          dark: '#5a8273',
          50: '#f6f8f7',
          100: '#eef2f0',
          200: '#dce5e0',
          300: '#b8ccc2',
          400: '#8fb3a3',
          500: '#6f9a8a',
          600: '#5a8273',
          700: '#4a6b5f',
        },
        'teal': {
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
        },
      },
      fontFamily: {
        heading: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', 'sans-serif'],
        body: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      borderRadius: {
        'sm': '8px',
        'md': '12px',
        'lg': '16px',
        'xl': '24px',
        '2xl': '32px',
      },
      boxShadow: {
        'soft-sm': '0 1px 2px rgba(74, 107, 95, 0.04), 0 1px 3px rgba(74, 107, 95, 0.06)',
        'soft-md': '0 4px 6px rgba(74, 107, 95, 0.05), 0 2px 4px rgba(74, 107, 95, 0.04)',
        'soft-lg': '0 10px 15px rgba(74, 107, 95, 0.06), 0 4px 6px rgba(74, 107, 95, 0.04)',
        'soft-xl': '0 20px 25px rgba(74, 107, 95, 0.08), 0 8px 10px rgba(74, 107, 95, 0.04)',
        'glow': '0 0 20px rgba(143, 179, 163, 0.25), 0 0 40px rgba(143, 179, 163, 0.15)',
        'glow-focus': '0 0 0 3px rgba(143, 179, 163, 0.2), 0 0 12px rgba(143, 179, 163, 0.15)',
        'glow-hover': '0 0 16px rgba(184, 204, 194, 0.3)',
      },
      backdropBlur: {
        'xs': '4px',
        'glass': '12px',
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'fade-out-down': 'fade-out-down 0.3s cubic-bezier(0.7, 0, 0.84, 0) forwards',
        'backdrop-in': 'backdrop-blur-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'backdrop-out': 'backdrop-blur-out 0.3s cubic-bezier(0.7, 0, 0.84, 0) forwards',
        'card-lift': 'card-lift 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'stagger-in': 'stagger-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'float-blob': 'float-blob 20s ease-in-out infinite',
        'border-shimmer': 'border-shimmer 3s linear infinite',
        'breathe': 'breathe 2s ease-in-out infinite',
        'ripple': 'ripple 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'gradient-shift': 'gradient-shift 8s ease infinite',
      },
      keyframes: {
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(12px) scale(0.98)' },
          to: { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'fade-out-down': {
          from: { opacity: '1', transform: 'translateY(0) scale(1)' },
          to: { opacity: '0', transform: 'translateY(8px) scale(0.98)' },
        },
        'backdrop-blur-in': {
          from: { backdropFilter: 'blur(0px)', backgroundColor: 'rgba(246, 248, 247, 0)' },
          to: { backdropFilter: 'blur(12px)', backgroundColor: 'rgba(246, 248, 247, 0.85)' },
        },
        'backdrop-blur-out': {
          from: { backdropFilter: 'blur(12px)', backgroundColor: 'rgba(246, 248, 247, 0.85)' },
          to: { backdropFilter: 'blur(0px)', backgroundColor: 'rgba(246, 248, 247, 0)' },
        },
        'card-lift': {
          from: { transform: 'translateY(0)', boxShadow: '0 1px 2px rgba(74, 107, 95, 0.04), 0 1px 3px rgba(74, 107, 95, 0.06)' },
          to: { transform: 'translateY(-4px)', boxShadow: '0 10px 15px rgba(74, 107, 95, 0.06), 0 4px 6px rgba(74, 107, 95, 0.04), 0 0 16px rgba(184, 204, 194, 0.3)' },
        },
        'stagger-in': {
          from: { opacity: '0', transform: 'translateX(-8px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'float-blob': {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '25%': { transform: 'translate(10px, -15px) scale(1.05)' },
          '50%': { transform: 'translate(-5px, 10px) scale(0.95)' },
          '75%': { transform: 'translate(-15px, -5px) scale(1.02)' },
        },
        'border-shimmer': {
          '0%': { backgroundPosition: '200% center' },
          '100%': { backgroundPosition: '-200% center' },
        },
        'breathe': {
          '0%, 100%': { opacity: '0.6', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.02)' },
        },
        'ripple': {
          '0%': { transform: 'scale(0)', opacity: '0.5' },
          '100%': { transform: 'scale(4)', opacity: '0' },
        },
        'gradient-shift': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
      },
      transitionTimingFunction: {
        'ease-out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'ease-in-expo': 'cubic-bezier(0.7, 0, 0.84, 0)',
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-main': 'linear-gradient(135deg, #f8f9f8 0%, #f6f8f7 50%, #eef2f0 100%)',
        'gradient-sidebar': 'linear-gradient(180deg, rgba(246, 248, 247, 0.95) 0%, rgba(238, 242, 240, 0.90) 100%)',
        'gradient-primary': 'linear-gradient(135deg, #b8ccc2 0%, #8fb3a3 50%, #6f9a8a 100%)',
        'gradient-glass': 'linear-gradient(135deg, rgba(255, 255, 255, 0.7) 0%, rgba(246, 248, 247, 0.5) 100%)',
        'gradient-aurora': 'linear-gradient(135deg, rgba(184, 204, 194, 0.4) 0%, rgba(56, 189, 248, 0.2) 25%, rgba(167, 139, 250, 0.2) 50%, rgba(184, 204, 194, 0.4) 75%, rgba(251, 191, 36, 0.2) 100%)',
      },
    },
  },
  plugins: [],
}
