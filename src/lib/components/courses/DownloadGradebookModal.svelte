<script lang="ts">
	import Modal from '../common/Modal.svelte';

	type Props = {
		show?: boolean;
		downloadError?: string | null;
		downloadCount?: number;
	};

	let {
		show = $bindable(false),
		downloadError = $bindable(null),
		downloadCount = $bindable(0)
	}: Props = $props();
</script>

<Modal bind:show size="sm">
	<div class="p-6">
		{#if downloadError}
			<!-- Error State -->
			<div class="text-center">
				<div
					class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30"
				>
					<svg
						class="h-8 w-8 text-red-600 dark:text-red-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						></path>
					</svg>
				</div>
				<h3 class="mb-2 text-lg font-semibold text-cisco-gray-90 dark:text-cisco-gray-10">
					Download Failed
				</h3>
				<p class="mb-4 text-sm text-cisco-gray-60 dark:text-cisco-gray-30">{downloadError}</p>
				<button
					onclick={() => {
						show = false;
						downloadError = null;
					}}
					class="rounded-lg bg-cisco-primary-blue px-4 py-2 text-white hover:bg-cisco-blue-60 dark:bg-cisco-primary-medium-blue dark:hover:bg-cisco-blue-50"
				>
					Close
				</button>
			</div>
		{:else}
			<!-- Loading State -->
			<div class="text-center">
				<div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center">
					<svg
						class="h-16 w-16 animate-spin text-cisco-primary-blue dark:text-cisco-light-blue-50"
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
				</div>
				<h3 class="mb-2 text-lg font-semibold text-cisco-gray-90 dark:text-cisco-gray-10">
					Downloading Gradebooks
				</h3>
				<p class="text-sm text-cisco-gray-60 dark:text-cisco-gray-30">
					Processing {downloadCount} course {downloadCount === 1 ? 'gradebook' : 'gradebooks'}...
				</p>
				<p class="mt-2 text-xs text-cisco-gray-50 dark:text-cisco-gray-40">
					This may take a few moments
				</p>
			</div>
		{/if}
	</div>
</Modal>
