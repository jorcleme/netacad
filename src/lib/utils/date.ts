/**
 * Convert Unix timestamp (seconds since epoch) to JavaScript Date
 */
export function fromUnixTimestamp(timestamp: number): Date {
	return new Date(timestamp * 1000);
}

/**
 * Format Unix timestamp as locale date string
 */
export function formatUnixDate(timestamp: number, locale = 'en-US'): string {
	return fromUnixTimestamp(timestamp).toLocaleDateString(locale);
}

/**
 * Format Unix timestamp as locale date and time string
 */
export function formatUnixDateTime(timestamp: number, locale = 'en-US'): string {
	return fromUnixTimestamp(timestamp).toLocaleString(locale);
}

/**
 * Format Unix timestamp as relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(timestamp: number): string {
	const date = fromUnixTimestamp(timestamp);
	const now = new Date();
	const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

	const intervals = {
		year: 31536000,
		month: 2592000,
		week: 604800,
		day: 86400,
		hour: 3600,
		minute: 60,
		second: 1
	};

	for (const [unit, secondsInUnit] of Object.entries(intervals)) {
		const interval = Math.floor(seconds / secondsInUnit);
		if (interval >= 1) {
			return `${interval} ${unit}${interval === 1 ? '' : 's'} ago`;
		}
	}

	return 'just now';
}

/**
 * Format ISO date string to locale date string
 */
export function formatISODate(isoString: string, locale = 'en-US'): string {
	return new Date(isoString).toLocaleDateString(locale, {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});
}

/**
 * Format course date range from ISO strings
 */
export function formatDateRange(startDate?: string, endDate?: string, locale = 'en-US'): string {
	if (!startDate && !endDate) {
		return 'No dates set';
	}

	if (!startDate && endDate) {
		return `Ends ${formatISODate(endDate, locale)}`;
	}

	if (startDate && !endDate) {
		return `Starts ${formatISODate(startDate, locale)}`;
	}

	// Both dates exist
	return `${formatISODate(startDate!, locale)} - ${formatISODate(endDate!, locale)}`;
}
