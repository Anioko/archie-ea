/**
 * core/01-logger.js — Unified logging and debugging module
 *
 * Requires: core/00-namespace.js
 *
 * Replaces:
 *   - Scattered console.log / console.error calls across all JS files
 *   - No centralised log level control
 *   - No production log suppression
 *
 * Usage:
 *   Platform.log.debug('Loading data', { page: 1 });
 *   Platform.log.info('User clicked save');
 *   Platform.log.warn('Deprecated function called', 'oldFn');
 *   Platform.log.error('Fetch failed', error);
 *   Platform.log.group('Modal lifecycle');
 *   Platform.log.groupEnd();
 *   Platform.log.time('render');
 *   Platform.log.timeEnd('render');
 *
 * Log levels (ascending severity):
 *   0 = DEBUG   (dev only)
 *   1 = INFO    (dev only)
 *   2 = WARN    (dev + prod)
 *   3 = ERROR   (dev + prod)
 *   4 = SILENT  (nothing)
 */

(function (global) {
    'use strict';

    if (!global.Platform) {
        throw new Error('[Platform] core/00-namespace.js must be loaded before core/01-logger.js');
    }

    let LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3, SILENT: 4 };
    let LEVEL_NAMES = ['DEBUG', 'INFO', 'WARN', 'ERROR'];

    // In development show everything; in production only WARN+
    let _currentLevel = global.Platform.isDev ? LEVELS.DEBUG : LEVELS.WARN;

    // Prefix for all log lines so they are easy to grep
    let PREFIX = '[Platform]';

    function _shouldLog(level) {
        return level >= _currentLevel;
    }

    function _format(level, args) {
        let label = LEVEL_NAMES[level] || '?';
        let parts = [PREFIX + '[' + label + ']'];
        for (let i = 0; i < args.length; i++) {
            parts.push(args[i]);
        }
        return parts;
    }

    let log = {
        /**
         * Set the minimum log level.
         * @param {'DEBUG'|'INFO'|'WARN'|'ERROR'|'SILENT'} levelName
         */
        setLevel: function (levelName) {
            let level = LEVELS[levelName.toUpperCase()];
            if (level === undefined) {
                throw new RangeError('[Platform.log] Unknown level: ' + levelName);
            }
            _currentLevel = level;
        },

        getLevel: function () {
            return LEVEL_NAMES[_currentLevel] || 'SILENT';
        },

        debug: function () {
            if (_shouldLog(LEVELS.DEBUG) && global.console && global.console.debug) {
                global.console.debug.apply(global.console, _format(LEVELS.DEBUG, arguments));
            }
        },

        info: function () {
            if (_shouldLog(LEVELS.INFO) && global.console && global.console.info) {
                global.console.info.apply(global.console, _format(LEVELS.INFO, arguments));
            }
        },

        warn: function () {
            if (_shouldLog(LEVELS.WARN) && global.console && global.console.warn) {
                global.console.warn.apply(global.console, _format(LEVELS.WARN, arguments));
            }
        },

        error: function () {
            if (_shouldLog(LEVELS.ERROR) && global.console && global.console.error) {
                global.console.error.apply(global.console, _format(LEVELS.ERROR, arguments));
            }
        },

        group: function (label) {
            if (_shouldLog(LEVELS.DEBUG) && global.console && global.console.group) {
                global.console.group(PREFIX + ' ' + label);
            }
        },

        groupEnd: function () {
            if (_shouldLog(LEVELS.DEBUG) && global.console && global.console.groupEnd) {
                global.console.groupEnd();
            }
        },

        time: function (label) {
            if (_shouldLog(LEVELS.DEBUG) && global.console && global.console.time) {
                global.console.time(PREFIX + ':' + label);
            }
        },

        timeEnd: function (label) {
            if (_shouldLog(LEVELS.DEBUG) && global.console && global.console.timeEnd) {
                global.console.timeEnd(PREFIX + ':' + label);
            }
        },

        /**
         * Create a child logger with a fixed sub-prefix.
         * @param {string} namespace  e.g. 'modal', 'fetch', 'pagination'
         * @returns {object} Logger with same API but prefixed messages
         */
        child: function (namespace) {
            let ns = '[' + namespace + ']';
            return {
                debug: function () {
                    if (_shouldLog(LEVELS.DEBUG) && global.console && global.console.debug) {
                        let args = [PREFIX + ns].concat(Array.prototype.slice.call(arguments));
                        global.console.debug.apply(global.console, args);
                    }
                },
                info: function () {
                    if (_shouldLog(LEVELS.INFO) && global.console && global.console.info) {
                        let args = [PREFIX + ns].concat(Array.prototype.slice.call(arguments));
                        global.console.info.apply(global.console, args);
                    }
                },
                warn: function () {
                    if (_shouldLog(LEVELS.WARN) && global.console && global.console.warn) {
                        let args = [PREFIX + ns].concat(Array.prototype.slice.call(arguments));
                        global.console.warn.apply(global.console, args);
                    }
                },
                error: function () {
                    if (_shouldLog(LEVELS.ERROR) && global.console && global.console.error) {
                        let args = [PREFIX + ns].concat(Array.prototype.slice.call(arguments));
                        global.console.error.apply(global.console, args);
                    }
                }
            };
        }
    };

    global.Platform.register('log', log);

}(window));
