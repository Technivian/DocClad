// Optional Tailwind extension for CLM One premium CLM design system.
// Merge this into tailwind.config.js if Tailwind is used.

module.exports = {
  theme: {
    extend: {
      colors: {
        dc: {
          navy: {
            950: '#07162c',
            900: '#0b1d36',
            850: '#102744',
            800: '#173250',
          },
          teal: {
            700: '#087f78',
            600: '#0b948b',
            500: '#17a79d',
            100: '#dff5f2',
            50: '#effbf9',
          },
          orange: {
            700: '#a8441f',
            600: '#bf4f27',
            500: '#d65a2c',
            100: '#fde8dc',
          },
          bg: '#f5f7fa',
          surface: '#ffffff',
          soft: '#fafbfc',
          border: '#dbe3ee',
          line: '#edf1f6',
          text: '#07162c',
          muted: '#53627a',
          subtle: '#7a879c',
          danger: '#c24132',
        },
      },
      borderRadius: {
        dcsm: '8px',
        dcmd: '10px',
        dclg: '14px',
      },
      boxShadow: {
        dccard: '0 1px 2px rgba(7, 22, 44, 0.04)',
        dcpopover: '0 12px 28px rgba(7, 22, 44, 0.12)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
    },
  },
};
