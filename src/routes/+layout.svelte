<script lang="ts">
	import '../app.css';
	import { onMount, tick } from 'svelte';
	import { Toaster, toast } from 'svelte-sonner';
	import { theme, user, socket, activeUserIds } from '$lib/stores';
	import favicon from '$lib/assets/favicon.svg';
	import Navbar from '$lib/components/layout/Navbar.svelte';
	import { goto } from '$app/navigation';
	import { getSessionUser } from '$lib/api/auths';
	import { page } from '$app/state';
	import { io } from 'socket.io-client';
	import { BASE_URL } from '$lib/constants';

	let { children } = $props();

	let loaded = $state(false);

	const setupSocket = async (enable: boolean = true) => {
		const _socket = io(`${BASE_URL}`, {
			reconnection: true,
			reconnectionDelay: 1000,
			reconnectionDelayMax: 5000,
			randomizationFactor: 0.5,
			path: '/ws/socket.io',
			transports: ['websocket'],
			auth: { token: localStorage.token }
		});

		socket.set(_socket);

		_socket.on('connect_error', (err) => {
			console.error('Socket connection error:', err);
		});

		_socket.on('connect', () => {
			console.log('Socket connected:', _socket.id);
		});
		_socket.on('reconnect_attempt', (attempt) => {
			console.log('reconnect_attempt', attempt);
		});

		_socket.on('reconnect_failed', () => {
			console.log('reconnect_failed');
		});

		_socket.on('disconnect', (reason, details) => {
			console.log(`Socket ${_socket.id} disconnected due to ${reason}`);
			if (details) {
				console.log('Additional details:', details);
			}
		});

		_socket.on('user-list', (data: { user_ids: string[] }) => {
			console.log('user-list', data);
			activeUserIds.set(data.user_ids);
		});
	};

	onMount(async () => {
		const currentPath = page.url.pathname;
		const isLoginPage = currentPath === '/login';

		await setupSocket();
		console.log('active User Ids: ', $activeUserIds);
		// Check if user has a token
		if (localStorage.token) {
			try {
				const sessionUser = await getSessionUser(localStorage.token);

				if (sessionUser) {
					$socket?.emit('user-join', { auth: { token: sessionUser.token } });
					user.set(sessionUser);

					// If on login page and authenticated, redirect to home
					if (isLoginPage) {
						await goto('/');
					}
				} else {
					// Token exists but invalid/expired
					localStorage.removeItem('token');
					user.set(null);

					if (!isLoginPage) {
						toast.error('Session expired. Please log in again.');
						await goto('/login');
					}
				}
			} catch (err) {
				// Token validation failed
				console.error('Session validation error:', err);
				localStorage.removeItem('token');
				user.set(null);

				if (!isLoginPage) {
					toast.error('Session expired. Please log in again.');
					await goto('/login');
				}
			}
		} else {
			// No token, user not authenticated
			user.set(null);

			if (!isLoginPage) {
				await goto('/login');
			}
		}

		await tick();
		loaded = true;
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Cisco | Netacad Gradebook Manager</title>
</svelte:head>

{#if loaded}
	<main class="h-screen max-h-dvh w-full font-cisco transition-all duration-200 ease-in-out">
		<Navbar />
		<div class="bg-theme-light p-4 dark:bg-theme-dark">
			{@render children?.()}
		</div>
	</main>
{:else}
	<!-- Loading state while checking authentication -->
	<div class="flex h-screen w-full items-center justify-center bg-theme-light dark:bg-theme-dark">
		<div class="flex flex-col items-center gap-4">
			<svg
				class="h-12 w-12 animate-spin text-cisco-primary-blue"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
			>
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
				></circle>
				<path
					class="opacity-75"
					fill="currentColor"
					d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
				></path>
			</svg>
			<p class="text-cisco-gray-60 dark:text-cisco-gray-40">Loading...</p>
		</div>
	</div>
{/if}

<Toaster
	theme={$theme.includes('dark')
		? 'dark'
		: $theme === 'system'
			? window.matchMedia('(prefers-color-scheme: dark)').matches
				? 'dark'
				: 'light'
			: 'light'}
	richColors
	position="top-center"
/>
