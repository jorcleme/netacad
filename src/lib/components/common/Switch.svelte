<script lang="ts">
	import { Switch } from 'bits-ui';

	type Props = {
		state?: boolean;
		onToggle?: () => void;
	};

	let { state = $bindable(true), onToggle }: Props = $props();

	function handleChange() {
		if (onToggle) {
			onToggle();
		}
	}
</script>

<Switch.Root
	bind:checked={state}
	onCheckedChange={handleChange}
	class="mx-px flex h-5 min-h-5 w-9 shrink-0 cursor-pointer items-center rounded-full px-[3px] transition  {state
		? ' bg-emerald-600'
		: 'bg-gray-200 dark:bg-transparent'} outline outline-gray-100 dark:outline-gray-800"
>
	<Switch.Thumb
		class="data-[state=unchecked]:shadow-mini pointer-events-none block size-4 shrink-0 rounded-full bg-white transition-transform data-[state=checked]:translate-x-3.5 data-[state=unchecked]:translate-x-0 "
	/>
</Switch.Root>
