import { API_BASE_URL } from '$lib/constants';

export const getSessionUser = async (token: string) => {
	let error = null;

	const response = await fetch(`${API_BASE_URL}/auths/session-user`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		credentials: 'include'
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

export const userSignOut = async () => {
	let error = null;

	await fetch(`${API_BASE_URL}/auths/signout`, {
		method: 'GET',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include'
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res;
		})
		.catch((err) => {
			console.log(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}
};
