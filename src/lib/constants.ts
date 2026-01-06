import { browser, dev } from '$app/environment';

export const APP_NAME = 'Netacad Gradebook Manager';
export const HOSTNAME = browser
	? dev
		? `${location.hostname}:8000`
		: `${location.hostname}:8000`
	: '';
export const BASE_URL = browser ? (dev ? `http://${HOSTNAME}` : ``) : ``;
export const API_BASE_URL = `${BASE_URL}/api/v1`;
