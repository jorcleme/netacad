<script lang="ts">
	import { type Snippet, onMount } from 'svelte';
	import { fade } from 'svelte/transition';

	import { userSignOut } from '$lib/api/auths';
	import { user, showSettings, activeUserIds, USAGE_POOL, theme } from '$lib/stores';
	import { DropdownMenu } from 'bits-ui';
	import Tooltip from './Tooltip.svelte';
	import Switch from './Switch.svelte';

	type Props = {
		show?: boolean;
		className?: string;
		trigger?: Snippet;
		content?: Snippet;
	};

	let { show = $bindable(false), className = 'max-w-[240px]', trigger, content }: Props = $props();

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

<DropdownMenu.Root
	bind:open={show}
	onOpenChange={(state) => {
		show = state;
	}}
>
	<DropdownMenu.Trigger>
		{@render trigger?.()}
	</DropdownMenu.Trigger>

	{#if content}
		<DropdownMenu.Content
			class="w-full {className} font-primary z-50 rounded-xl bg-white px-1 py-1.5 text-sm shadow-lg dark:bg-gray-850 dark:text-white"
			sideOffset={8}
			side="bottom"
			align="start"
		>
			{@render content?.()}
		</DropdownMenu.Content>
	{:else}
		<DropdownMenu.Content
			class="w-full {className} font-primary z-50 rounded-xl bg-white px-1 py-1.5 text-sm shadow-lg dark:bg-gray-850 dark:text-white"
			sideOffset={8}
			side="bottom"
			align="start"
		>
			<button
				data-tour="settings"
				class="flex w-full rounded-md px-3 py-2 transition hover:bg-gray-50 dark:hover:bg-gray-800"
				onclick={() => {
					showSettings.set(true);
					show = false;

					// if ($mobile) {
					// 	showSidebar.set(false);
					// }
				}}
			>
				<div class="mr-3 self-center">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-5 w-5"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.107-1.204l-.527-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z"
						/>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
						/>
					</svg>
				</div>
				<div class=" self-center truncate">Settings</div>
			</button>

			<hr class=" my-1 border-gray-100 p-0 dark:border-gray-850" />

			<button
				class="flex w-full rounded-md px-3 py-2 transition hover:bg-gray-50 dark:hover:bg-gray-800"
				onclick={async () => {
					await userSignOut();
					user.set(null);

					localStorage.removeItem('token');
					location.href = '/login';

					show = false;
				}}
			>
				<div class="mr-3 self-center">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 20 20"
						fill="currentColor"
						class="h-5 w-5"
					>
						<path
							fill-rule="evenodd"
							d="M3 4.25A2.25 2.25 0 015.25 2h5.5A2.25 2.25 0 0113 4.25v2a.75.75 0 01-1.5 0v-2a.75.75 0 00-.75-.75h-5.5a.75.75 0 00-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 00.75-.75v-2a.75.75 0 011.5 0v2A2.25 2.25 0 0110.75 18h-5.5A2.25 2.25 0 013 15.75V4.25z"
							clip-rule="evenodd"
						/>
						<path
							fill-rule="evenodd"
							d="M6 10a.75.75 0 01.75-.75h9.546l-1.048-.943a.75.75 0 111.004-1.114l2.5 2.25a.75.75 0 010 1.114l-2.5 2.25a.75.75 0 11-1.004-1.114l1.048-.943H6.75A.75.75 0 016 10z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
				<div class=" self-center truncate">Sign Out</div>
			</button>

			<hr class=" my-1 border-gray-100 p-0 dark:border-gray-850" />
			<div class="flex items-center justify-between px-3 py-2">
				<div class=" self-center">Theme</div>
				<Switch bind:state={isDarkMode} onToggle={handleThemeToggle} />
			</div>

			{#if ($activeUserIds?.length ?? 0) > 0}
				<hr class=" my-1 border-gray-100 p-0 dark:border-gray-850" />

				<Tooltip
					content={$USAGE_POOL && $USAGE_POOL.length > 0
						? `Running: ${$USAGE_POOL.join(', ')} ✨`
						: ''}
				>
					<div class="flex items-center gap-2.5 rounded-md px-3 py-1.5 text-xs">
						<div class=" flex items-center">
							<span class="relative flex size-2">
								<span
									class="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75"
								></span>
								<span class="relative inline-flex size-2 rounded-full bg-green-500"></span>
							</span>
						</div>

						<div class=" ">
							<span class=""> Active Users </span>
							<span class=" font-semibold">
								{$activeUserIds?.length}
							</span>
						</div>
					</div>
				</Tooltip>
			{/if}
		</DropdownMenu.Content>
	{/if}
</DropdownMenu.Root>
