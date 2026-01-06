<script lang="ts">
	import type { Course } from '$lib/types';
	import { formatDateRange } from '$lib/utils/date';

	type Props = {
		courses: Course[];
		selectionMode?: boolean;
		selectedCourseIds?: Set<string>;
		toggleCourseSelection?: (courseId: string) => void;
		downloadSingleGradebook?: (course: Course) => void;
	};

	let {
		courses,
		selectionMode = false,
		selectedCourseIds = new Set(),
		toggleCourseSelection = () => {},
		downloadSingleGradebook = () => {}
	}: Props = $props();
</script>

<div class="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
	{#each courses as course (course.id)}
		<div
			class="group relative overflow-hidden rounded-lg bg-white p-5 dark:glass-bg-dark {selectedCourseIds.has(
				course.id
			)
				? 'border-cisco-primary-blue ring-2 ring-cisco-primary-blue/20 dark:border-cisco-light-blue-50 dark:ring-cisco-light-blue-50/20'
				: 'border-cisco-gray-15 dark:border-cisco-gray-60'}"
		>
			<!-- Selection Checkbox (top-left when in selection mode) -->
			{#if selectionMode}
				<div class="absolute top-3 left-3 z-10">
					<input
						type="checkbox"
						checked={selectedCourseIds.has(course.id)}
						onchange={() => toggleCourseSelection(course.id)}
						class="cursor-pointer"
						aria-label={`Select ${course.name}`}
					/>
				</div>
			{/if}

			<!-- Status Badge -->
			<div class="absolute top-3 right-3">
				<span
					class="rounded-full px-2 py-1 font-inter text-xs font-bold {course.status === 'active'
						? 'bg-green-100 text-green-800'
						: course.status === 'inactive'
							? 'bg-yellow-100 text-yellow-800'
							: 'bg-gray-100 text-gray-800'}"
				>
					{course.status}
				</span>
			</div>

			<!-- Course Icon -->
			<div
				class="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-cisco-blue-05 text-cisco-primary-blue dark:bg-cisco-gray-70 dark:text-cisco-light-blue-50"
			>
				<svg class="h-6 w-6" fill="currentColor" viewBox="0 0 20 20">
					<path
						d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3zM3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-.89 11.115 11.115 0 01.25-3.762zM9.3 16.573A9.026 9.026 0 007 14.935v-3.957l1.818.78a3 3 0 002.364 0l5.508-2.361a11.026 11.026 0 01.25 3.762 1 1 0 01-.89.89 8.968 8.968 0 00-5.35 2.524 1 1 0 01-1.4 0zM6 18a1 1 0 001-1v-2.065a8.935 8.935 0 00-2-.712V17a1 1 0 001 1z"
					></path>
				</svg>
			</div>

			<!-- Course Info -->
			<h3
				class="mb-2 font-semibold text-cisco-gray-90 group-hover:text-cisco-primary-blue dark:text-cisco-gray-10 dark:group-hover:text-cisco-light-blue-50"
			>
				{course.name}
			</h3>

			<p class="mb-3 text-sm font-semibold text-cisco-gray-60 dark:text-cisco-gray-30">
				ID: <span class="font-mono">{course.course_id}</span>
			</p>

			<!-- Action Buttons -->
			<div class="mb-3 flex items-center gap-2">
				{#if course.url}
					<a
						href={course.url}
						target="_blank"
						rel="noopener noreferrer"
						class="inline-flex items-center gap-1 text-sm font-semibold text-blue-700 hover:underline dark:text-cisco-primary-blue"
					>
						View Course
						<svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
							<path
								d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z"
							></path>
							<path
								d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z"
							></path>
						</svg>
					</a>
				{/if}

				{#if !selectionMode}
					<button
						onclick={() => downloadSingleGradebook(course)}
						class="ml-auto inline-flex items-center gap-1 rounded-md bg-cisco-light-blue-05 px-2 py-1 text-xs font-semibold text-cisco-blue-70 transition hover:bg-cisco-light-blue-10 dark:bg-cisco-gray-70 dark:text-cisco-primary-blue dark:hover:bg-cisco-gray-60"
						aria-label={`Download gradebook for ${course.name}`}
					>
						<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
							></path>
						</svg>
						Gradebook
					</button>
				{/if}
			</div>

			<!-- Course date range -->
			<div
				class="border-t border-cisco-gray-10 pt-3 text-xs text-gray-600 dark:border-cisco-gray-70 dark:text-gray-50"
			>
				{formatDateRange(course.start_date, course.end_date)}
			</div>
		</div>
	{/each}
</div>
