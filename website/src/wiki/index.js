import enUS from './articles.en-US'
import ptBR from './articles.pt-BR'

const articlesByLocale = { 'en-US': enUS, 'pt-BR': ptBR }

export function getArticles(locale) {
  return articlesByLocale[locale] || enUS
}

export function getArticle(locale, slug) {
  return getArticles(locale).find((a) => a.slug === slug) || null
}
