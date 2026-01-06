import type { Course, SortOption } from '$lib/types';

/**
 * Extracts the numeric prefix from a course name
 * E.g., "3758 Software Cisco Business Dashboard Lite 2.11.0" -> 3758
 */
function extractCourseNumber(courseName: string): number {
	const match = courseName.match(/^(\d+)/);
	return match ? parseInt(match[1], 10) : 0;
}

/**
 * Sorts an array of courses based on the selected sort option
 */
export function sortCourses(courses: Course[], sortOption: SortOption): Course[] {
	const sorted = [...courses]; // Create a copy to avoid mutating the original

	switch (sortOption) {
		case 'name-asc':
			return sorted.sort((a, b) => {
				const numA = extractCourseNumber(a.name);
				const numB = extractCourseNumber(b.name);
				if (numA !== numB) return numA - numB;
				return a.name.localeCompare(b.name);
			});

		case 'name-desc':
			return sorted.sort((a, b) => {
				const numA = extractCourseNumber(a.name);
				const numB = extractCourseNumber(b.name);
				if (numA !== numB) return numB - numA;
				return b.name.localeCompare(a.name);
			});

		case 'start-date-asc':
			return sorted.sort((a, b) => {
				// Courses without start_date go to the end
				if (!a.start_date && !b.start_date) return 0;
				if (!a.start_date) return 1;
				if (!b.start_date) return -1;
				return new Date(a.start_date).getTime() - new Date(b.start_date).getTime();
			});

		case 'start-date-desc':
			return sorted.sort((a, b) => {
				// Courses without start_date go to the end
				if (!a.start_date && !b.start_date) return 0;
				if (!a.start_date) return 1;
				if (!b.start_date) return -1;
				return new Date(b.start_date).getTime() - new Date(a.start_date).getTime();
			});

		case 'end-date-asc':
			return sorted.sort((a, b) => {
				// Courses without end_date go to the end
				if (!a.end_date && !b.end_date) return 0;
				if (!a.end_date) return 1;
				if (!b.end_date) return -1;
				return new Date(a.end_date).getTime() - new Date(b.end_date).getTime();
			});

		case 'end-date-desc':
			return sorted.sort((a, b) => {
				// Courses without end_date go to the end
				if (!a.end_date && !b.end_date) return 0;
				if (!a.end_date) return 1;
				if (!b.end_date) return -1;
				return new Date(b.end_date).getTime() - new Date(a.end_date).getTime();
			});
		case 'created-asc':
			return sorted.sort((a, b) => a.created_at - b.created_at);

		case 'created-desc':
			return sorted.sort((a, b) => b.created_at - a.created_at);

		default:
			return sorted;
	}
}

/**
 * Get human-readable label for sort option
 */
export function getSortLabel(sortOption: SortOption): string {
	const labels: Record<SortOption, string> = {
		'name-asc': 'Course Number (Low to High)',
		'name-desc': 'Course Number (High to Low)',
		'start-date-asc': 'Start Date (Oldest First)',
		'start-date-desc': 'Start Date (Newest First)',
		'end-date-asc': 'End Date (Oldest First)',
		'end-date-desc': 'End Date (Newest First)',
		'created-asc': 'Date Added (Oldest First)',
		'created-desc': 'Date Added (Newest First)'
	};
	return labels[sortOption];
}
