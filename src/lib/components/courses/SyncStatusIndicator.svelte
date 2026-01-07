<script lang="ts">
	import { getSyncStatus } from '$lib/api/courses';
	import type { SyncStatusResponse } from '$lib/types';
	import { toast } from 'svelte-sonner';
	import { onMount } from 'svelte';

	interface Props {
		syncId: string;
		onComplete?: (status: SyncStatusResponse) => void;
		onError?: (error: string) => void;
	}

	let { syncId, onComplete, onError }: Props = $props();

	let status = $state<SyncStatusResponse | null>(null);
	let isChecking = $state(false);
	let isSyncComplete = $state(false);

	async function checkStatus() {
		if (isChecking) return; // Prevent double-clicking
		
		isChecking = true;
		try {
			const response = await getSyncStatus(syncId);
			status = response;

			// Check if sync is complete or failed
			if (response.status === 'completed' || response.status === 'failed') {
				isSyncComplete = true;

				// Trigger callbacks
				if (response.status === 'completed') {
					toast.success(
						`Sync completed! ${response.new_courses} new, ${response.updated_courses} updated`
					);
					onComplete?.(response);
				} else if (response.status === 'failed') {
					const errorMsg = response.error_message || 'Sync failed. Please try again.';
					toast.error(errorMsg);
					onError?.(errorMsg);
				}
			}
		} catch (err) {
			console.error('Error checking sync status:', err);
			toast.error('Failed to check sync status. Please try again.');
		} finally {
			isChecking = false;
		}
	}

	onMount(async () => {
		// Check status once on mount
		await checkStatus();
	});



	function formatDuration(seconds: number | undefined): string {
		if (!seconds) return '0s';
		if (seconds < 60) return `${seconds}s`;
		const minutes = Math.floor(seconds / 60);
		const remainingSeconds = seconds % 60;
		return `${minutes}m ${remainingSeconds}s`;
	}

	const statusIcon = $derived.by(() => {
		if (!status) return 'processing';
		return status.status;
	});

	const statusColor = $derived.by(() => {
		if (!status) return 'blue';
		switch (status.status) {
			case 'completed':
				return 'green';
			case 'failed':
				return 'red';
			case 'processing':
				return 'blue';
			default:
				return 'gray';
		}
	});
</script>

<div
	class="rounded-lg glass-bg p-4 shadow-lg transition-all duration-300 {statusColor === 'green'
		? 'border-2 border-green-500'
		: statusColor === 'red'
			? 'border-2 border-red-500'
			: 'border-2 border-cisco-primary-blue'}"
>
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-3">
			<!-- Status Icon -->
			{#if statusIcon === 'processing'}
				<svg
					class="h-6 w-6 animate-spin text-cisco-primary-blue"
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
			{:else if statusIcon === 'completed'}
				<svg class="h-6 w-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
					></path>
				</svg>
			{:else if statusIcon === 'failed'}
				<svg class="h-6 w-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
					></path>
				</svg>
			{/if}

			<!-- Status Text -->
			<div>
				<div class="flex items-center gap-2">
					<span class="font-semibold text-cisco-gray-80 dark:text-white">
						{#if statusIcon === 'processing'}
							Syncing courses...
						{:else if statusIcon === 'completed'}
							Sync completed successfully
						{:else if statusIcon === 'failed'}
							Sync failed
						{/if}
					</span>
					{#if status?.duration}
						<span class="text-sm text-cisco-gray-50 dark:text-cisco-gray-40">
							({formatDuration(status.duration)})
						</span>
					{/if}
				</div>

				{#if status}
					<div
						class="mt-1 flex items-center gap-4 text-sm text-cisco-gray-60 dark:text-cisco-gray-30"
					>
						{#if status.status === 'processing'}
							<span>Scraping courses from NetAcad...</span>
						{:else if status.status === 'completed'}
							<span class="text-green-600 dark:text-green-400">
								✓ {status.total_scraped} courses scraped
							</span>
							{#if status.new_courses > 0}
								<span class="text-cisco-primary-blue dark:text-cisco-light-blue-50">
									+{status.new_courses} new
								</span>
							{/if}
							{#if status.updated_courses > 0}
								<span class="text-orange-500">↻ {status.updated_courses} updated</span>
							{/if}
						{:else if status.status === 'failed'}
							<span class="text-red-600 dark:text-red-400">
								{status.error_message || 'An error occurred during sync'}
							</span>
						{/if}
					</div>
				{/if}
			</div>
		</div>

		<!-- Check Status Button (always visible when not complete) -->
		{#if !isSyncComplete}
			<button
				onclick={checkStatus}
				disabled={isChecking}
				class="flex items-center gap-2 rounded-full px-4 py-2 font-medium text-cisco-primary-blue transition hover:bg-cisco-blue-05 disabled:cursor-not-allowed disabled:opacity-50 dark:text-cisco-light-blue-50 dark:hover:bg-cisco-gray-70"
				aria-label="Check sync status"
			>
				{#if isChecking}
					<svg
						class="h-5 w-5 animate-spin"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
					>
						<circle
							class="opacity-25"
							cx="12"
							cy="12"
							r="10"
							stroke="currentColor"
							stroke-width="4"
						></circle>
						<path
							class="opacity-75"
							fill="currentColor"
							d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
						></path>
					</svg>
					<span>Checking...</span>
				{:else}
					<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						></path>
					</svg>
					<span>Check Status</span>
				{/if}
			</button>
		{/if}
	</div>
</div>
