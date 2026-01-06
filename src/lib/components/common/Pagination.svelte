<script lang="ts">
	import { Pagination } from 'bits-ui';
	import CaretLeft from 'phosphor-svelte/lib/CaretLeft';
	import CaretRight from 'phosphor-svelte/lib/CaretRight';

	type Props = {
		count: number;
		perPage: number;
		currentPage?: number;
		onPageChange?: (page: number) => void;
	};

	let { count, perPage, currentPage = 1, onPageChange }: Props = $props();
</script>

<Pagination.Root {count} {perPage} page={currentPage} {onPageChange}>
	{#snippet children({ pages, range })}
		<div class="my-8 flex items-center justify-center">
			<Pagination.PrevButton
				class="mr-[25px] inline-flex size-10 items-center justify-center rounded-[9px] bg-transparent hover:bg-cisco-gray-40 active:scale-[0.98] disabled:cursor-not-allowed disabled:text-gray-400 hover:disabled:bg-transparent dark:text-cisco-gray-10 dark:hover:bg-cisco-gray-60 dark:disabled:text-cisco-gray-50"
			>
				<CaretLeft class="size-6" />
			</Pagination.PrevButton>
			<div class="flex items-center gap-2.5">
				{#each pages as page (page.key)}
					{#if page.type === 'ellipsis'}
						<div class="text-[15px] font-medium select-none dark:text-cisco-gray-10">...</div>
					{:else}
						<Pagination.Page
							{page}
							class="inline-flex size-10 items-center justify-center rounded-[9px] bg-transparent text-[15px] font-medium select-none hover:bg-cisco-gray-40 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 hover:disabled:bg-transparent data-selected:bg-cisco-gray-30 data-selected:text-white dark:text-cisco-gray-10 dark:hover:bg-cisco-gray-60 dark:data-selected:bg-cisco-primary-blue"
						>
							{page.value}
						</Pagination.Page>
					{/if}
				{/each}
			</div>
			<Pagination.NextButton
				class="ml-[29px] inline-flex size-10 items-center justify-center rounded-[9px] bg-transparent hover:bg-cisco-gray-40 active:scale-[0.98] disabled:cursor-not-allowed disabled:text-cisco-gray-15 hover:disabled:bg-transparent dark:text-cisco-gray-10 dark:hover:bg-cisco-gray-60 dark:disabled:text-cisco-gray-50"
			>
				<CaretRight class="size-6" />
			</Pagination.NextButton>
		</div>
		<p class="text-center text-[13px] text-cisco-gray-90 dark:text-cisco-gray-10">
			Showing {range.start} - {range.end}
		</p>
	{/snippet}
</Pagination.Root>
