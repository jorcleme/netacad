import type { AllCourseResponse, SyncCoursesResponse, SyncStatusResponse } from '$lib/types';

export const getAllCourses = async (
	skip = 0,
	limit = 100,
	status?: string
): Promise<AllCourseResponse | null> => {
	let error = null;

	// Build URL with optional status parameter
	const params = new URLSearchParams({
		skip: skip.toString(),
		limit: limit.toString()
	});

	if (status) {
		params.append('status', status);
	}

	const response = await fetch(`http://localhost:8000/api/v1/courses/?${params.toString()}`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json'
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return await res.json();
		})
		.catch((err) => {
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return response;
};

export const syncCoursesFromNetacad = async (): Promise<SyncCoursesResponse> => {
	let error = null;

	const response = await fetch(`http://localhost:8000/api/v1/courses/sync`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return await res.json();
		})
		.catch((err) => {
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return response;
};

export const getSyncStatus = async (syncId?: string): Promise<SyncStatusResponse> => {
	let error = null;

	const queryParams = new URLSearchParams();

	if (syncId) {
		queryParams.append('sync_id', syncId);
	}

	const url = syncId
		? `http://localhost:8000/api/v1/courses/sync/status?${queryParams.toString()}`
		: `http://localhost:8000/api/v1/courses/sync/status`;

	const response = await fetch(url, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json'
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return await res.json();
		})
		.catch((err) => {
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return response;
};

export interface GradebookDownloadRequest {
	course_id: string;
	course_name: string;
	course_url: string;
}

export interface GradebookDownloadResponse {
	success: boolean;
	course_id: string;
	course_name: string;
	csv_path?: string;
	markdown_path?: string;
	error?: string;
}

export const downloadGradebook = async (
	course_id: string,
	course_name: string,
	course_url: string
): Promise<Blob> => {
	const response = await fetch(`http://localhost:8000/api/v1/courses/gradebook/download`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({
			course_id,
			course_name,
			course_url
		})
	});

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({ detail: 'Download failed' }));
		throw new Error(errorData.detail || 'Failed to download gradebook');
	}

	// Return the blob (CSV file)
	return await response.blob();
};

export const downloadMultipleGradebooks = async (
	courses: GradebookDownloadRequest[]
): Promise<Blob> => {
	try {
		console.log('[API] Sending request to download gradebooks...');
		const response = await fetch(`http://localhost:8000/api/v1/courses/gradebook/download/bulk`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({
				courses
			})
		});

		console.log('[API] Response status:', response.status, response.statusText);
		console.log('[API] Response headers:', {
			contentType: response.headers.get('content-type'),
			contentDisposition: response.headers.get('content-disposition'),
			contentLength: response.headers.get('content-length')
		});

		if (!response.ok) {
			console.log('[API] Response not OK, reading error text...');
			// Check content-type to determine how to read the error
			const contentType = response.headers.get('content-type') || '';
			let errorText = '';

			if (contentType.includes('application/json')) {
				try {
					const errorJson = await response.json();
					errorText = JSON.stringify(errorJson);
				} catch {
					errorText = 'Failed to parse error response';
				}
			} else {
				errorText = await response.text();
			}

			console.log('[API] Error text:', errorText);
			throw new Error(`Failed to download gradebooks: ${response.statusText} - ${errorText}`);
		}

		console.log('[API] Converting response to blob...');
		const blob = await response.blob();
		console.log('[API] Blob created:', blob.type, blob.size, 'bytes');
		return blob;
	} catch (error) {
		console.error('[API] Error in downloadMultipleGradebooks:', error);
		// Log the error type to help debug
		if (error instanceof SyntaxError) {
			console.error('[API] SyntaxError detected - likely attempted to parse non-JSON response');
		}
		throw error;
	}
};

export const getGradebookFile = async (
	fileType: 'csv' | 'markdown',
	filename: string
): Promise<Blob> => {
	const response = await fetch(
		`http://localhost:8000/api/v1/courses/gradebook/file/${fileType}/${filename}`
	);

	if (!response.ok) {
		throw new Error(`Failed to download file: ${response.statusText}`);
	}

	return await response.blob();
};
