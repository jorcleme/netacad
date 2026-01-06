<script lang="ts">
	import type { Theme } from '$lib/types/stores';
	import { onMount } from 'svelte';
	import { theme } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	let themes = $state<string[]>(['light', 'dark']);
	let selectedTheme = $state<Theme>('system');

	const applyTheme = (_theme: Theme) => {
		let themeToApply = _theme;

		if (_theme === 'system') {
			themeToApply = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
		}

		themes
			.filter((t) => t !== themeToApply)
			.forEach((t) => {
				t.split(' ').forEach((e) => {
					document.documentElement.classList.remove(e);
				});
			});

		themeToApply.split(' ').forEach((e) => {
			document.documentElement.classList.add(e);
		});

		console.log(_theme);
	};

	const themeChangeHandler = (_theme: Theme) => {
		theme.set(_theme);
		localStorage.setItem('theme', _theme);
		applyTheme(_theme);
	};

	const saveHandler = () => {
		toast.success('Settings saved!');
	};

	onMount(async () => {
		selectedTheme = (localStorage.getItem('theme') as Theme) || ('system' as Theme);
	});
</script>

<div class="flex h-full flex-col justify-between text-sm">
	<div class="max-h-112 overflow-y-scroll lg:max-h-full">
		<div class="flex flex-col space-y-2">
			<div class="mb-1 text-sm font-medium">Settings</div>

			<div class="flex w-full justify-between">
				<div class="self-center text-xs font-medium">Theme</div>
				<div class="relative flex items-center">
					<select
						class="w-fit rounded-sm bg-transparent px-2 py-2 pr-8 text-right text-xs outline-hidden dark:bg-gray-900"
						bind:value={selectedTheme}
						placeholder="Select a theme"
						onchange={() => themeChangeHandler(selectedTheme)}
					>
						<option value="system">⚙️ System</option>
						<option value="dark">🌑 Dark</option>
						<option value="light">☀️ Light</option>
					</select>
				</div>
			</div>

			<!-- <div class=" flex w-full justify-between">
				<div class=" self-center text-xs font-medium">{$i18n.t('Language')}</div>
				<div class="relative flex items-center">
					<select
						class=" w-fit rounded-sm bg-transparent px-2 py-2 pr-8 text-right text-xs outline-hidden dark:bg-gray-900"
						bind:value={lang}
						placeholder="Select a language"
						on:change={(e) => {
							changeLanguage(lang);
						}}
					>
						{#each languages as language}
							<option value={language['code']}>{language['title']}</option>
						{/each}
					</select>
				</div>
			</div>
			{#if $i18n.language === 'en-US'}
				<div class="mb-2 text-xs text-gray-400 dark:text-gray-500">
					Couldn't find your language?
					<a
						class=" font-medium text-gray-300 underline"
						href="https://github.com/open-webui/open-webui/blob/main/docs/CONTRIBUTING.md#-translations-and-internationalization"
						target="_blank"
					>
						Help us translate Open WebUI!
					</a>
				</div>
			{/if} -->
		</div>
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="rounded-full bg-black px-3.5 py-1.5 text-sm font-medium text-white transition hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100"
			onclick={() => {
				saveHandler();
			}}
		>
			Save
		</button>
	</div>
</div>
