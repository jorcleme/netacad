export type Course = {
	id: string;
	course_id: string;
	name: string;
	url: string;
	status: 'active' | 'inactive' | 'archived';
	created_at: number; // Unix timestamp (seconds since epoch)
	updated_at: number; // Unix timestamp (seconds since epoch)
	start_date?: string; // ISO 8601 date string
	end_date?: string; // ISO 8601 date string
};

export type SortOption =
	| 'name-asc'
	| 'name-desc'
	| 'start-date-asc'
	| 'start-date-desc'
	| 'end-date-asc'
	| 'end-date-desc'
	| 'created-asc'
	| 'created-desc';

export type AllCourseResponse = {
	courses: Course[];
	total: number;
	skip: number;
	limit: number;
	has_more: boolean;
};

export type SyncCoursesResponse = {
	sync_id: string;
	message: string;
	status: string;
	started_at: number;
};

export type SyncStatusResponse = {
	id: string;
	status: 'idle' | 'processing' | 'completed' | 'failed';
	started_at: number;
	completed_at?: number;
	duration?: number;
	total_scraped: number;
	new_courses: number;
	existing_courses: number;
	updated_courses: number;
	failed_courses: number;
	error_message?: string;
};
