<script lang="ts">
	import FileArrowUp from 'phosphor-svelte/lib/FileArrowUp';

	type Props = {
		classname?: string;
		color?: string;
	};

	let { classname = 'w-4 h-4', color = 'currentColor' }: Props = $props();
</script>

<FileArrowUp class={classname} {color} />
