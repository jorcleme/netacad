<script lang="ts">
	import type { Snippet } from 'svelte';
	import { DropdownMenu } from 'bits-ui';

	type Side = 'top' | 'bottom' | 'left' | 'right';
	type Align = 'start' | 'center' | 'end';

	type Props = {
		show?: boolean;
		side?: Side;
		align?: Align;
		trigger: Snippet;
		content: Snippet;
	};
	let {
		show = $bindable(false),
		side = 'bottom',
		align = 'start',
		trigger,
		content
	}: Props = $props();
</script>

<DropdownMenu.Root
	bind:open={show}
	onOpenChange={(state) => {
		show = state;
	}}
>
	<DropdownMenu.Trigger>
		{@render trigger()}
	</DropdownMenu.Trigger>
	{#if content}
		<DropdownMenu.Content
			sideOffset={8}
			side="bottom"
			align="start"
			class="z-50 w-full max-w-36 rounded-lg border border-cisco-gray-90 bg-cisco-gray-05 px-1 py-1.5 text-gray-900 dark:bg-cisco-gray-80 dark:text-white"
		>
			{@render content()}
		</DropdownMenu.Content>
	{:else}
		<DropdownMenu.Content
			class="z-50 w-full max-w-36 rounded-lg border border-cisco-gray-90 bg-cisco-gray-05 px-1 py-1.5 text-gray-900 dark:bg-cisco-gray-80 dark:text-white"
			sideOffset={8}
			{side}
			{align}
		>
			<DropdownMenu.Item class="flex items-center px-3 py-2 text-sm  font-medium">
				<div class="flex items-center">Profile</div>
			</DropdownMenu.Item>

			<DropdownMenu.Item class="flex items-center px-3 py-2 text-sm  font-medium">
				<div class="flex items-center">Profile</div>
			</DropdownMenu.Item>

			<DropdownMenu.Item class="flex items-center px-3 py-2 text-sm  font-medium">
				<div class="flex items-center">Profile</div>
			</DropdownMenu.Item>
		</DropdownMenu.Content>
	{/if}
</DropdownMenu.Root>
