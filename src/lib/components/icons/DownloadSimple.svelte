<script lang="ts">
	import DownloadSimple from 'phosphor-svelte/lib/DownloadSimple';

	type Props = {
		classname?: string;
		color?: string;
	};

	let { classname = 'w-4 h-4', color = 'currentColor' }: Props = $props();
</script>

<DownloadSimple class={classname} {color} />
