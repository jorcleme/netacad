<script lang="ts">
	import { onDestroy, type Snippet } from 'svelte';

	import DOMPurify from 'dompurify';
	import type { Instance, SingleTarget } from 'tippy.js';
	import tippy from 'tippy.js';
	import type { Placement } from 'tippy.js';

	type Props = {
		placement?: Placement;
		content?: string;
		touch?: boolean;
		className?: string;
		theme?: string;
		offset?: [number, number];
		allowHTML?: boolean;
		tippyOptions?: Record<string, any>;
		children: Snippet;
	};

	let {
		placement = 'top',
		content = '',
		touch = false,
		className = '',
		theme = 'dark',
		offset = [0, 8],
		allowHTML = true,
		tippyOptions = {},
		children
	}: Props = $props();

	let tooltipElement: SingleTarget | null = $state(null);
	let tooltipInstance: Instance;

	$effect(() => {
		if (tooltipElement && content) {
			if (tooltipInstance) {
				tooltipInstance.setContent(DOMPurify.sanitize(content));
			} else {
				tooltipInstance = tippy(tooltipElement as SingleTarget, {
					content: DOMPurify.sanitize(content),
					placement: placement,
					allowHTML: allowHTML,
					touch: touch,
					...(theme !== '' ? { theme } : { theme: 'dark' }),
					arrow: false,
					offset: offset,
					...tippyOptions
				});
			}
		} else if (tooltipInstance && content === '') {
			if (tooltipInstance) {
				tooltipInstance.destroy();
			}
		}
	});

	onDestroy(() => {
		if (tooltipInstance) {
			tooltipInstance.destroy();
		}
	});
</script>

<div bind:this={tooltipElement} aria-label={content} class={className}>
	{@render children?.()}
</div>
