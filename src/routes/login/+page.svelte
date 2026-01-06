<script lang="ts">
	import type { SessionUser } from '$lib/stores';
	import { user, socket } from '$lib/stores';
	import { BASE_URL } from '$lib/constants';
	import { getSessionUser } from '$lib/api/auths';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';

	let loaded = $state(false);

	const setSessionUser = async (sessionUser: SessionUser) => {
		if (sessionUser) {
			toast.success(`Welcome, ${sessionUser.name}!`);
			if (sessionUser.token) {
				localStorage.setItem('token', sessionUser.token);
			}
			$socket?.emit('user-join', { auth: { token: sessionUser.token } });
			user.set(sessionUser);
			await goto('/');
		}
	};

	const checkOAuthCallback = async () => {
		if (!page.url.hash) return;

		const hash = page.url.hash.substring(1); // Remove the '#' character
		if (!hash) return;

		const params = new URLSearchParams(hash);
		const token = params.get('token');
		if (!token) return;

		console.log('OAuth token received, validating...');

		try {
			const sessionUser = await getSessionUser(token);

			if (sessionUser) {
				localStorage.setItem('token', token);
				await setSessionUser(sessionUser);
			} else {
				toast.error('Failed to authenticate. Please try again.');
			}
		} catch (err) {
			console.error('OAuth callback error:', err);
			toast.error('Authentication failed. Please try again.');
			// Clear any existing token
			localStorage.removeItem('token');
			user.set(null);
		}
	};

	$effect(() => {
		checkOAuthCallback();
		// If user is already authenticated, redirect to home
		if ($user && loaded) {
			goto('/');
		}
	});

	onMount(async () => {
		loaded = true;
		await checkOAuthCallback();
	});
</script>

<div class="relative max-h-dvh w-full p-4 text-white">
	{#if loaded}
		<div
			class="flex min-h-screen w-full justify-center bg-theme-light p-4 text-gray-900 dark:bg-theme-dark dark:text-white"
		>
			<div class="flex min-h-full w-full flex-col px-10 text-center sm:max-w-md">
				<div class="my-auto w-full pb-10 dark:text-gray-100">
					<div class="inline-flex w-full items-center justify-center">
						<hr class="my-4 h-px w-32 border-0 bg-gray-700/10 dark:bg-gray-100/10" />
						<h1 class="mx-4 text-2xl font-semibold">Sign in to NetAcad Manager</h1>
						<hr class="my-4 h-px w-32 border-0 bg-gray-700/10 dark:bg-gray-100/10" />
					</div>
					<div class="mt-4 flex flex-col space-y-2">
						<button
							class="flex w-full items-center justify-center rounded-full bg-gray-700/5 py-2.5 text-sm font-medium transition hover:bg-gray-700/10 dark:bg-gray-100/5 dark:text-gray-300 dark:hover:bg-gray-100/10 dark:hover:text-white"
							onclick={() => {
								window.location.href = `${BASE_URL}/oauth/oidc/login`;
							}}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="1.5"
								stroke="currentColor"
								class="mr-3 size-6"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"
								/>
							</svg>

							<span class="font-bold">Continue with Cisco SSO</span>
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>
