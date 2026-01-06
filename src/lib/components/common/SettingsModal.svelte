<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Modal from './Modal.svelte';
	import Search from '../icons/Search.svelte';
	import General from './Settings/General.svelte';

	type Props = {
		show?: boolean;
	};

	let { show = $bindable(false) }: Props = $props();

	let selectedTab = $state<string>('general');

	interface SettingsTab {
		id: string;
		title: string;
		keywords: string[];
	}

	const searchData: SettingsTab[] = [
		{
			id: 'general',
			title: 'General',
			keywords: [
				'general',
				'theme',
				'language',
				'notifications',
				'system',
				'systemprompt',
				'prompt',
				'advanced',
				'settings',
				'defaultsettings',
				'configuration',
				'systemsettings',
				'notificationsettings',
				'systempromptconfig',
				'languageoptions',
				'defaultparameters',
				'systemparameters'
			]
		},
		{
			id: 'interface',
			title: 'Interface',
			keywords: [
				'defaultmodel',
				'selectmodel',
				'ui',
				'userinterface',
				'display',
				'layout',
				'design',
				'landingpage',
				'landingpagemode',
				'default',
				'chat',
				'chatbubble',
				'chatui',
				'username',
				'showusername',
				'displayusername',
				'widescreen',
				'widescreenmode',
				'fullscreen',
				'expandmode',
				'chatdirection',
				'lefttoright',
				'ltr',
				'righttoleft',
				'rtl',
				'notifications',
				'toast',
				'toastnotifications',
				'largechunks',
				'streamlargechunks',
				'scroll',
				'scrollonbranchchange',
				'scrollbehavior',
				'richtext',
				'richtextinput',
				'background',
				'chatbackground',
				'chatbackgroundimage',
				'backgroundimage',
				'uploadbackground',
				'resetbackground',
				'titleautogen',
				'titleautogeneration',
				'autotitle',
				'chattags',
				'autochattags',
				'responseautocopy',
				'clipboard',
				'location',
				'userlocation',
				'userlocationaccess',
				'haptic',
				'hapticfeedback',
				'vibration',
				'voice',
				'voicecontrol',
				'voiceinterruption',
				'call',
				'emojis',
				'displayemoji',
				'save',
				'interfaceoptions',
				'interfacecustomization',
				'alwaysonwebsearch'
			]
		},
		{
			id: 'connections',
			title: 'Connections',
			keywords: []
		},
		{
			id: 'tools',
			title: 'Tools',
			keywords: []
		},
		{
			id: 'personalization',
			title: 'Personalization',
			keywords: [
				'personalization',
				'memory',
				'personalize',
				'preferences',
				'profile',
				'personalsettings',
				'customsettings',
				'userpreferences',
				'accountpreferences'
			]
		},
		{
			id: 'audio',
			title: 'Audio',
			keywords: [
				'audio',
				'sound',
				'soundsettings',
				'audiocontrol',
				'volume',
				'speech',
				'speechrecognition',
				'stt',
				'speechtotext',
				'tts',
				'texttospeech',
				'playback',
				'playbackspeed',
				'voiceplayback',
				'speechplayback',
				'audiooutput',
				'speechengine',
				'voicecontrol',
				'audioplayback',
				'transcription',
				'autotranscribe',
				'autosend',
				'speechsettings',
				'audiovoice',
				'voiceoptions',
				'setvoice',
				'nonlocalvoices',
				'savesettings',
				'audioconfig',
				'speechconfig',
				'voicerecognition',
				'speechsynthesis',
				'speechmode',
				'voicespeed',
				'speechrate',
				'speechspeed',
				'audioinput',
				'audiofeatures',
				'voicemodes'
			]
		},
		{
			id: 'chats',
			title: 'Chats',
			keywords: [
				'chat',
				'messages',
				'conversations',
				'chatsettings',
				'history',
				'chathistory',
				'messagehistory',
				'messagearchive',
				'convo',
				'chats',
				'conversationhistory',
				'exportmessages',
				'chatactivity'
			]
		},
		{
			id: 'account',
			title: 'Account',
			keywords: [
				'account',
				'profile',
				'security',
				'privacy',
				'settings',
				'login',
				'useraccount',
				'userdata',
				'api',
				'apikey',
				'userprofile',
				'profiledetails',
				'accountsettings',
				'accountpreferences',
				'securitysettings',
				'privacysettings'
			]
		},
		{
			id: 'admin',
			title: 'Admin',
			keywords: [
				'admin',
				'administrator',
				'adminsettings',
				'adminpanel',
				'systemadmin',
				'administratoraccess',
				'systemcontrol',
				'manage',
				'management',
				'admincontrols',
				'adminfeatures',
				'usercontrol',
				'arenamodel',
				'evaluations',
				'websearch',
				'database',
				'pipelines',
				'images',
				'audio',
				'documents',
				'rag',
				'models',
				'ollama',
				'openai',
				'users'
			]
		},
		{
			id: 'articles',
			title: 'Articles',
			keywords: [
				'articles',
				'user articles',
				'saved articles',
				'saved',
				'articlefeatures',
				'articlesettings'
			]
		},
		{
			id: 'about',
			title: 'About',
			keywords: [
				'about',
				'info',
				'information',
				'version',
				'documentation',
				'help',
				'support',
				'details',
				'aboutus',
				'softwareinfo',
				'timothyjaeryangbaek',
				'openwebui',
				'release',
				'updates',
				'updateinfo',
				'versioninfo',
				'aboutapp',
				'terms',
				'termsandconditions',
				'contact',
				'aboutpage'
			]
		}
	];

	let search = $state<string>('');
	let visibleTabs = $state<string[]>(searchData.map((tab) => tab.id));
	let searchDebounceTimeout: number | NodeJS.Timeout = $state(0);

	const searchSettings = (query: string): string[] => {
		const lowerCaseQuery = query.toLowerCase().trim();
		return searchData
			.filter(
				(tab) =>
					tab.title.toLowerCase().includes(lowerCaseQuery) ||
					tab.keywords.some((keyword) => keyword.includes(lowerCaseQuery))
			)
			.map((tab) => tab.id);
	};

	const searchDebounceHandler = () => {
		clearTimeout(searchDebounceTimeout);
		searchDebounceTimeout = setTimeout(() => {
			visibleTabs = searchSettings(search);
			if (visibleTabs.length > 0 && !visibleTabs.includes(selectedTab)) {
				selectedTab = visibleTabs[0];
			}
		}, 100);
	};
</script>

<Modal size="xl" bind:show>
	<div class="text-gray-700 dark:text-gray-100">
		<div class=" flex justify-between px-5 pt-4 pb-1 dark:text-gray-300">
			<div class=" self-center text-lg font-medium">Settings</div>
			<button
				class="self-center"
				aria-label="Close settings modal"
				onclick={() => {
					show = false;
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="h-5 w-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>

		<div class="flex w-full flex-col px-4 pt-1 pb-4 md:flex-row md:space-x-4">
			<div
				id="settings-tabs-container"
				class="tabs mb-1 flex flex-1 -translate-y-1 flex-row gap-2.5 overflow-x-auto text-left text-sm font-medium md:mb-0 md:w-40 md:flex-none md:flex-col md:gap-1 dark:text-gray-200"
			>
				<div class="-mb-1 hidden w-full gap-2 rounded-xl px-0.5 md:flex" id="settings-search">
					<div class="self-center rounded-l-xl bg-transparent">
						<Search classname="size-3.5" />
					</div>
					<input
						class="w-full rounded-md bg-transparent py-1.5 text-sm outline-hidden dark:text-gray-300"
						bind:value={search}
						oninput={searchDebounceHandler}
						placeholder="Search"
					/>
				</div>

				{#if visibleTabs.length > 0}
					{#each visibleTabs as tabId (tabId)}
						{#if tabId === 'general'}
							<button
								class="flex min-w-fit flex-1 rounded-lg px-0.5 py-1 text-left transition md:flex-none {selectedTab ===
								'general'
									? ''
									: 'text-gray-300 hover:text-gray-700 dark:text-gray-600 dark:hover:text-white'}"
								onclick={() => {
									selectedTab = 'general';
								}}
							>
								<div class=" mr-2 self-center">
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="h-4 w-4"
									>
										<path
											fill-rule="evenodd"
											d="M8.34 1.804A1 1 0 019.32 1h1.36a1 1 0 01.98.804l.295 1.473c.497.144.971.342 1.416.587l1.25-.834a1 1 0 011.262.125l.962.962a1 1 0 01.125 1.262l-.834 1.25c.245.445.443.919.587 1.416l1.473.294a1 1 0 01.804.98v1.361a1 1 0 01-.804.98l-1.473.295a6.95 6.95 0 01-.587 1.416l.834 1.25a1 1 0 01-.125 1.262l-.962.962a1 1 0 01-1.262.125l-1.25-.834a6.953 6.953 0 01-1.416.587l-.294 1.473a1 1 0 01-.98.804H9.32a1 1 0 01-.98-.804l-.295-1.473a6.957 6.957 0 01-1.416-.587l-1.25.834a1 1 0 01-1.262-.125l-.962-.962a1 1 0 01-.125-1.262l.834-1.25a6.957 6.957 0 01-.587-1.416l-1.473-.294A1 1 0 011 10.68V9.32a1 1 0 01.804-.98l1.473-.295c.144-.497.342-.971.587-1.416l-.834-1.25a1 1 0 01.125-1.262l.962-.962A1 1 0 015.38 3.03l1.25.834a6.957 6.957 0 011.416-.587l.294-1.473zM13 10a3 3 0 11-6 0 3 3 0 016 0z"
											clip-rule="evenodd"
										/>
									</svg>
								</div>
								<div class=" self-center">General</div>
							</button>
						{/if}
					{/each}
				{:else}
					<div class="mt-4 text-center text-gray-500">No Results Found</div>
				{/if}
			</div>
			<div class="max-h-128 flex-1 md:min-h-128">
				{#if selectedTab === 'general'}
					<General />
				{/if}
			</div>
		</div>
	</div>
</Modal>
