/**
 * @typedef {Object} ErrorEvent
 * @property {number} [id]
 * @property {string} word
 * @property {string} [suggestion]
 * @property {string} [context]
 * @property {string} [corrected_context]
 * @property {string} [country_code]
 * @property {string} [country_name]
 * @property {string} [url]
 * @property {string} [title]
 * @property {string} [timestamp]
 */

/**
 * @typedef {Object} NewsArticle
 * @property {number} [id]
 * @property {string} url
 * @property {string} [title]
 * @property {string} [country_code]
 * @property {string} [content]
 * @property {string} [published_at]
 * @property {number} [word_count]
 */

/**
 * @typedef {Object} GlobalStats
 * @property {number} total_errors
 * @property {number} total_words
 * @property {number} active_countries
 * @property {string} timestamp
 */

/**
 * @typedef {Object} TimelinePoint
 * @property {string} timestamp
 * @property {number} count
 */

/**
 * @typedef {Object} HeatmapPoint
 * @property {number} lat
 * @property {number} lng
 * @property {number} intensity
 */

export {};
