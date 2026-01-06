export const hasInnerDetails = (error: unknown): error is { details: string } => {
	return (
		error != null &&
		typeof error === 'object' &&
		'details' in error &&
		typeof error.details === 'string'
	);
};

export const hasInnerMessage = (error: unknown): error is { message: string } => {
	return (
		error != null &&
		typeof error === 'object' &&
		'message' in error &&
		typeof error.message === 'string'
	);
};

// Write a utility function that checks if error is of type Error
