import { motion } from 'framer-motion'

export function AppFooter() {
  return (
    <motion.footer
      className="app-footer"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, ease: 'easeOut', delay: 0.1 }}
    >
      v{__APP_VERSION__} · Made with ❤️ for <a href="http://dml.ir/" target="_blank" rel="noopener noreferrer">DML</a>
    </motion.footer>
  )
}
