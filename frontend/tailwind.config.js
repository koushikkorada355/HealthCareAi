/** MediConnect theme — vital blue + apricot on cool clinical canvas.
 *  @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#1E6FF5',
          deep: '#123E9C',
          ink: '#0C2B6B',
          soft: '#E4EEFE',
          mist: '#F2F6FD',
        },
        ink: { DEFAULT: '#101F2E', soft: '#51606F', faint: '#8CA0B3' },
        canvas: '#F3F6FA',
        apricot: { DEFAULT: '#FF8A3D', soft: '#FFEEDF', deep: '#C85A12' },
        mint: { DEFAULT: '#12B981', soft: '#DDF7EA', deep: '#0B7A55' },
        success: '#16A34A',
        warn: '#D97706',
        crit: '#DC2626',
        // legacy aliases (old teal theme) → mapped so untouched pages keep working
        teal: { DEFAULT: '#1E6FF5', deep: '#123E9C', soft: '#E4EEFE' },
        cream: '#F3F6FA',
        coral: '#FF8A3D',
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        display: ['Fraunces', 'Georgia', 'serif'],
      },
      boxShadow: {
        card: '0 10px 28px rgba(16,31,46,.09)',
        lift: '0 16px 40px rgba(30,111,245,.18)',
      },
      borderRadius: { xl2: '16px' },
      keyframes: {
        'fade-up': { from: { opacity: 0, transform: 'translateY(10px)' }, to: { opacity: 1, transform: 'none' } },
        'fade-in': { from: { opacity: 0 }, to: { opacity: 1 } },
        'pop-in': { '0%': { opacity: 0, transform: 'scale(.96)' }, '100%': { opacity: 1, transform: 'scale(1)' } },
        float: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-8px)' } },
        'pulse-ring': {
          '0%': { boxShadow: '0 0 0 0 rgba(255,138,61,.45)' },
          '70%': { boxShadow: '0 0 0 20px rgba(255,138,61,0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(255,138,61,0)' },
        },
        shimmer: { '0%': { backgroundPosition: '-400px 0' }, '100%': { backgroundPosition: '400px 0' } },
        'slide-in': { from: { opacity: 0, transform: 'translateX(14px)' }, to: { opacity: 1, transform: 'none' } },
      },
      animation: {
        'fade-up': 'fade-up .45s cubic-bezier(.22,.68,.32,1) both',
        'fade-in': 'fade-in .3s ease both',
        'pop-in': 'pop-in .28s cubic-bezier(.22,.68,.32,1.2) both',
        float: 'float 5s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 2s ease-out infinite',
        'slide-in': 'slide-in .3s ease both',
      },
    },
  },
  plugins: [],
}
