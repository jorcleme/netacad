<script lang="ts">
	import type { Snippet } from 'svelte';
	import { onDestroy } from 'svelte';
	import { fade } from 'svelte/transition';
	import { flyAndScale } from '$lib/utils/transitions';

	type Size = 'full' | 'xs' | 'sm' | 'md' | 'lg' | 'xl';

	type Props = {
		show?: boolean;
		size?: Size;
		modalClassname?: string;
		containerClassname?: string;
		children: Snippet;
	};

	let {
		show = $bindable(true),
		size = 'md',
		modalClassname = 'fixed top-0 right-0 bottom-0 left-0',
		containerClassname = 'bg-white dark:bg-cisco-gray-80 dark:border dark:border-cisco-gray-60 rounded-2xl',
		children
	}: Props = $props();

	let modal = $state<HTMLDivElement | null>(null);

	const sizeToTailwindWidth = (size: Size) => {
		switch (size) {
			case 'full':
				return 'w-full';
			case 'xs':
				return 'w-64';
			case 'sm':
				return 'w-120';
			case 'md':
				return 'w-2xl';
			default:
				return 'w-4xl';
		}
	};

	const isTopModal = () => {
		const modals = document.getElementsByClassName('modal');
		return modals.length && modals[modals.length - 1] === modal;
	};

	const handleKeyDown = (e: KeyboardEvent) => {
		if (e.key === 'Escape' && isTopModal()) {
			show = false;
		}
	};

	$effect(() => {
		if (show && modal) {
			document.body.appendChild(modal);
			window.addEventListener('keydown', handleKeyDown);
			document.body.style.overflow = 'hidden';
		} else if (modal) {
			window.removeEventListener('keydown', handleKeyDown);
			if (document.body.contains(modal)) {
				document.body.removeChild(modal);
			}
			document.body.style.overflow = 'unset';
		}
	});

	onDestroy(() => {
		show = false;
		if (modal && document.body.contains(modal)) {
			document.body.removeChild(modal);
		}
	});
</script>

{#if show}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		bind:this={modal}
		class="modal {modalClassname} z-9999 flex h-screen max-h-dvh w-full justify-center overflow-y-auto overscroll-contain bg-black/60 p-4"
		in:fade={{ duration: 10 }}
		onmousedown={() => {
			show = false;
		}}
	>
		<div
			class="m-auto max-w-full {sizeToTailwindWidth(size)} {size !== 'full'
				? 'mx-2'
				: ''} shadow-3xl scrollbar-hidden min-h-fit {containerClassname}"
			in:flyAndScale
			onmousedown={(e) => {
				e.stopPropagation();
			}}
		>
			{@render children?.()}
		</div>
	</div>
{/if}
