<script lang="ts">
	import X from 'phosphor-svelte/lib/X';

	type Props = {
		classname?: string;
		color?: string;
	};

	let { classname = 'w-4 h-4', color = 'currentColor' }: Props = $props();
</script>

<X class={classname} {color} />
