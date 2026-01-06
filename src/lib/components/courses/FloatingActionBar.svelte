<script lang="ts">
	import { flyAndScale } from '$lib/utils/transitions';
	import DownloadSimple from '../icons/DownloadSimple.svelte';
	import X from '../icons/X.svelte';

	type Props = {
		selectedCount: number;
		downloadGradebooks: () => void;
		clearSelection: () => void;
	};

	let { selectedCount, downloadGradebooks, clearSelection }: Props = $props();
</script>

<div
	in:flyAndScale
	class="fixed bottom-4 left-1/2 z-50 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 transform px-4 transition-all duration-300 sm:bottom-8 sm:w-full sm:px-0"
>
	<div
		class="flex flex-col items-center gap-3 rounded-lg bg-black/90 px-4 py-3 shadow-2xl sm:flex-row sm:justify-around sm:gap-4 sm:px-6 sm:py-4"
	>
		<!-- Selection Count -->
		<div class="flex items-center gap-2 text-white">
			<span
				class="flex h-8 w-8 items-center justify-center rounded-full border border-cisco-primary-blue bg-cisco-primary-midnight-blue p-3 font-cisco-thin text-sm leading-none text-white sm:h-5 sm:w-5 sm:p-4"
			>
				{selectedCount}
			</span>
			<span class="font-cisco-thin text-xs font-bold sm:text-sm">
				{selectedCount === 1 ? 'course' : 'courses'} selected
			</span>
		</div>

		<!-- Divider (hidden on mobile, shown on larger screens) -->
		<div class="hidden h-8 w-px bg-cisco-gray-40 sm:block"></div>

		<!-- Actions -->
		<div class="flex w-full items-center justify-center gap-2 sm:w-auto">
			<!-- Download Gradebooks Button -->
			<button
				onclick={downloadGradebooks}
				class="flex flex-1 items-center justify-center gap-2 rounded-lg bg-cisco-primary-blue px-3 py-2 font-cisco-thin text-sm text-white transition hover:bg-cisco-blue-60 sm:flex-initial sm:px-4"
			>
				<DownloadSimple classname="h-4 w-4 sm:h-5 sm:w-5" />
				<span class="hidden sm:inline"
					>{selectedCount > 0 ? 'Download Gradebook' : 'Download Gradebooks'}</span
				>
				<span class="sm:hidden">Get</span>
			</button>

			<!-- Clear Selection Button -->
			<button
				onclick={clearSelection}
				class="flex flex-1 items-center justify-center gap-2 rounded-lg border border-cisco-gray-40 px-3 py-2 font-cisco-thin text-sm text-white transition hover:bg-cisco-gray-80 sm:flex-initial sm:px-4"
				aria-label="Clear selection"
			>
				<X classname="h-4 w-4 sm:h-5 sm:w-5" />
				<span class="hidden sm:inline">Clear</span>
			</button>
		</div>
	</div>
</div>
