<script lang="ts">
	import logo from '$lib/assets/cisco_logo_pantone_400.png';
	import darkLogo from '$lib/assets/cisco_logo_white_400.png';
	import SettingsModal from '../common/SettingsModal.svelte';
	import Switch from '../common/Switch.svelte';
	import { theme, user } from '$lib/stores';
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import UserMenu from '../common/UserMenu.svelte';

	let showSettings = $state(false);
	let isDarkMode = $state(false);

	onMount(() => {
		// Initialize theme system
		const cleanup = theme.init();

		// Subscribe to theme changes
		const unsubscribe = theme.subscribe((value) => {
			if (value === 'system') {
				// Check system preference
				isDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
			} else {
				isDarkMode = value === 'dark';
			}
		});

		return () => {
			cleanup?.();
			unsubscribe();
		};
	});

	function handleThemeToggle() {
		theme.toggle();
	}
</script>

<nav
	class="min-h-16 w-full bg-white p-2 shadow-sm dark:border-b dark:border-cisco-gray-70 dark:bg-theme-dark"
>
	<div class="flex h-full min-h-16 items-center justify-between">
		<div class="flex items-center gap-4">
			<img src={isDarkMode ? darkLogo : logo} alt="Cisco Logo" class="h-8 w-auto" />
			<a
				href="/"
				class="font-bold text-cisco-blue-90 transition hover:text-cisco-primary-blue dark:text-cisco-gray-10 dark:hover:text-cisco-light-blue-50"
				>Home</a
			>
			<a
				href="/courses"
				class="font-bold text-cisco-blue-90 transition hover:text-cisco-primary-blue dark:text-cisco-gray-10 dark:hover:text-cisco-light-blue-50"
				>Courses</a
			>
		</div>
		{#if $user}
			<div class="flex items-center">
				<UserMenu>
					{#snippet trigger()}
						<button
							class="flex w-full rounded-xl p-1.5 transition select-none hover:bg-gray-50 dark:hover:bg-gray-850"
							aria-label="User Menu"
							data-tour="settings"
						>
							<div class=" self-center">
								<img
									src="/user.png"
									class="size-6 rounded-full object-cover"
									alt="User profile"
									draggable="false"
								/>
							</div>
						</button>
					{/snippet}
				</UserMenu>
			</div>
		{/if}
	</div>
</nav>

<SettingsModal bind:show={showSettings} />
