import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import de from './de.json'
import en from './en.json'

const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('revly-locale') : null

i18n.use(initReactI18next).init({
  resources: { de: { translation: de }, en: { translation: en } },
  lng: stored || 'de',
  fallbackLng: 'de',
  interpolation: { escapeValue: false },
})

export function setLocale(locale: 'de' | 'en') {
  void i18n.changeLanguage(locale)
  localStorage.setItem('revly-locale', locale)
}

export default i18n
