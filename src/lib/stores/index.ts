import type { Theme } from '$lib/types/stores';
import type { Socket } from 'socket.io-client';
import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export interface SessionUser {
	id: string;
	name: string;
	email: string;
	last_active_at?: number; // epoch time in seconds
	oauth_sub?: string;
	updated_at: number; // epoch time in seconds
	created_at: number; // epoch time in seconds
	settings?: Record<string, unknown>; // user settings/preferences
	token?: string; // JWT token for API authentication
}

function createThemeStore() {
	// Initialize from localStorage or default to 'system'
	const initialTheme: Theme = browser
		? (localStorage.getItem('theme') as Theme) || 'system'
		: 'system';

	const { subscribe, set, update } = writable<Theme>(initialTheme);

	return {
		subscribe,
		set: (value: Theme) => {
			if (browser) {
				localStorage.setItem('theme', value);
				applyTheme(value);
			}
			set(value);
		},
		toggle: () => {
			update((current) => {
				const next = current === 'dark' ? 'light' : 'dark';
				if (browser) {
					localStorage.setItem('theme', next);
					applyTheme(next);
				}
				return next;
			});
		},
		init: () => {
			if (browser) {
				applyTheme(initialTheme);

				// Listen for system theme changes
				const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
				const handleChange = () => {
					const currentTheme = localStorage.getItem('theme') as Theme;
					if (currentTheme === 'system') {
						applyTheme('system');
					}
				};

				mediaQuery.addEventListener('change', handleChange);

				return () => mediaQuery.removeEventListener('change', handleChange);
			}
		}
	};
}

function applyTheme(theme: Theme) {
	if (!browser) return;

	const root = document.documentElement;
	const isDark =
		theme === 'dark' ||
		(theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

	if (isDark) {
		root.classList.add('dark');
		root.classList.remove('light');
	} else {
		root.classList.add('light');
		root.classList.remove('dark');
	}
}

export const theme = createThemeStore();
export const user = writable<SessionUser | null>(null);
export const socket = writable<Socket | null>(null);
export const showSettings = writable<boolean>(false);
export const activeUserIds = writable<string[]>([]);
export const USAGE_POOL = writable<string[] | null>(null);
