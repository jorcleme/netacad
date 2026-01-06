<script lang="ts">
	import type { Course, SortOption, SyncStatusResponse } from '$lib/types';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Pagination from '$lib/components/common/Pagination.svelte';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import FileArrowUp from '$lib/components/icons/FileArrowUp.svelte';
	import DownloadGradebookModal from '$lib/components/courses/DownloadGradebookModal.svelte';
	import FloatingActionBar from '$lib/components/courses/FloatingActionBar.svelte';
	import Courses from '$lib/components/courses/Courses.svelte';
	import SyncStatusIndicator from '$lib/components/courses/SyncStatusIndicator.svelte';
	import { hasInnerDetails, hasInnerMessage } from '$lib/utils';
	import { sortCourses } from '$lib/utils/sort';
	import {
		getAllCourses,
		syncCoursesFromNetacad,
		downloadGradebook,
		downloadMultipleGradebooks
	} from '$lib/api/courses';
	import intersight from '$lib/assets/illustration_intersight.png';
	import { user } from '$lib/stores';
	import { goto } from '$app/navigation';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import X from '$lib/components/icons/X.svelte';

	// State
	let courses = $state<Course[]>([]);
	let showActionsDropdown = $state(false);
	let loading = $state(false);
	let syncing = $state(false);
	let currentSyncId = $state<string | null>(null);
	let showSyncStatus = $state(false);

	// Pagination state
	let currentPage = $state(1);
	let pageSize = $state(20);
	let totalCourses = $state(0);
	let hasMore = $state(false);

	// Filter and Sort state
	let searchQuery = $state('');
	let sortOption = $state<SortOption>('name-asc');

	// File upload state
	let fileInput = $state<HTMLInputElement>();
	let files = $state<FileList | null>(null);
	let uploadedFile = $state<File | null>(null);

	// Selection state for bulk actions
	let selectedCourseIds = $state<Set<string>>(new Set());
	let selectionMode = $state(false);
	let selectAllPages = $state(false); // Track if selecting all pages

	// Download state
	let downloadingGradebooks = $state(false);
	let downloadCount = $state(0);
	let downloadError = $state<string | null>(null);

	// Computed
	const totalPages = $derived(Math.ceil(totalCourses / pageSize));
	const selectedCount = $derived(selectedCourseIds.size);

	const filteredCourses = $derived.by(() => {
		// First filter by search query
		const filtered = courses.filter((course) => {
			const matchesSearch = course.name.toLowerCase().includes(searchQuery.toLowerCase());
			return matchesSearch;
		});

		// Then sort the filtered results
		return sortCourses(filtered, sortOption);
	});

	const allVisibleSelected = $derived(
		filteredCourses.length > 0 &&
			filteredCourses.every((course) => selectedCourseIds.has(course.id))
	);

	// Authentication guard - protect sensitive course data
	$effect(() => {
		if (!$user) {
			toast.error('Authentication required to view courses');
			goto('/login');
		}
	});

	onMount(() => {
		// Only load courses if user is authenticated
		if ($user) {
			loadCourses();
		}
	});

	async function loadCourses() {
		loading = true;

		try {
			const skip = (currentPage - 1) * pageSize;

			const response = await getAllCourses(skip, pageSize);

			if (response) {
				courses = response.courses;
				totalCourses = response.total;
				hasMore = response.has_more;
			}
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'Failed to load courses';
			toast.error(errorMessage);
			console.error('Error loading courses:', err);
		} finally {
			loading = false;
		}
	}

	async function handleSync() {
		syncing = true;
		showSyncStatus = false;

		try {
			const res = await syncCoursesFromNetacad();
			currentSyncId = res.sync_id;
			showSyncStatus = true;
			toast.info('Course sync started. Checking status...');
		} catch (err) {
			if (hasInnerDetails(err)) {
				toast.error(err.details);
			} else if (hasInnerMessage(err)) {
				toast.error(err.message);
			} else if (err instanceof Error) {
				toast.error(`${err.name}: ${err.message}`);
			}
		} finally {
			syncing = false;
		}
	}

	function handleSyncComplete(status: SyncStatusResponse) {
		showSyncStatus = false;
		currentSyncId = null;
		// Reload courses after successful sync
		loadCourses();
	}

	function handleSyncError(error: string) {
		// Keep the status indicator visible so user can see the error
		// It will auto-hide after they acknowledge it
		setTimeout(() => {
			showSyncStatus = false;
			currentSyncId = null;
		}, 5000);
	}

	function handleFileSelect(event: Event & { currentTarget: EventTarget & HTMLInputElement }) {
		const target = event.currentTarget;
		const file = target.files?.[0];

		if (file) {
			uploadedFile = file;
			console.log('File selected:', file.name);
			// TODO: Process file upload
		}
	}

	function clearFile() {
		uploadedFile = null;
		if (fileInput) {
			fileInput.value = '';
		}
	}

	function goToPage(page: number) {
		if (page >= 1 && page <= totalPages) {
			currentPage = page;
			loadCourses();
		}
	}

	function toggleSelectionMode() {
		selectionMode = !selectionMode;
		if (!selectionMode) {
			selectedCourseIds.clear();
			selectAllPages = false;
			selectedCourseIds = new Set(); // Force reactivity
		}
	}

	function toggleCourseSelection(courseId: string) {
		const newSelection = new Set(selectedCourseIds);
		if (newSelection.has(courseId)) {
			newSelection.delete(courseId);
			selectAllPages = false; // User deselected something, so not all pages selected
		} else {
			newSelection.add(courseId);
		}
		selectedCourseIds = newSelection; // Create new Set to trigger reactivity
	}

	function toggleSelectAll() {
		const newSelection = new Set(selectedCourseIds);
		if (allVisibleSelected) {
			// Deselect all visible
			filteredCourses.forEach((course) => newSelection.delete(course.id));
		} else {
			// Select all visible
			filteredCourses.forEach((course) => newSelection.add(course.id));
		}
		selectedCourseIds = newSelection; // Create new Set to trigger reactivity
	}

	async function selectAllCourses() {
		loading = true;
		try {
			// Fetch ALL courses (no pagination limit)
			const response = await getAllCourses(0, totalCourses);

			if (response) {
				// Create new Set with all course IDs
				const allIds = new Set(response.courses.map((c) => c.id));
				selectedCourseIds = allIds;
				selectAllPages = true;
				console.log(`Selected all ${allIds.size} courses across all pages`);
			}
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'Failed to load all courses';
			toast.error(errorMessage);
			console.error('Error loading all courses:', err);
		} finally {
			loading = false;
		}
	}

	function clearSelection() {
		selectedCourseIds = new Set(); // Create new Set to trigger reactivity
		selectAllPages = false;
	}

	async function downloadGradebooks() {
		if (selectedCount === 0) return;

		downloadingGradebooks = true;
		downloadError = null;

		try {
			let selectedCourses: Course[] = [];

			// If all pages are selected, fetch all courses
			if (selectAllPages) {
				const response = await getAllCourses(0, totalCourses);
				if (response) {
					selectedCourses = response.courses;
				}
				console.log(`Downloading gradebooks for ALL ${selectedCourses.length} courses...`);
			} else {
				// Fetch all courses to get full details for selected IDs (selections may span multiple pages)
				const response = await getAllCourses(0, totalCourses);
				if (response) {
					// Filter to only selected course IDs
					selectedCourses = response.courses.filter((c) => selectedCourseIds.has(c.id));
				}
				console.log(`Downloading gradebooks for ${selectedCourses.length} selected courses...`);
			}

			downloadCount = selectedCourses.length;

			const coursesData = selectedCourses.map((course) => ({
				course_id: course.course_id,
				course_name: course.name,
				course_url: course.url
			}));

			// Call API to download gradebooks (returns zip file as blob)
			console.log('Calling API to download gradebooks...');
			const zipBlob = await downloadMultipleGradebooks(coursesData);
			console.log('Received blob:', zipBlob.type, zipBlob.size, 'bytes');

			// Create download link and trigger download
			const url = window.URL.createObjectURL(zipBlob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `netacad_gradebooks_${new Date().toISOString().replace(/[:.]/g, '-')}.zip`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			window.URL.revokeObjectURL(url);

			console.log('Download triggered successfully');

			// Close modal after successful download
			downloadingGradebooks = false;

			// Clear selection after download
			clearSelection();

			toast.success(`Successfully downloaded ${selectedCourses.length} gradebook(s)`);
		} catch (err) {
			downloadError = err instanceof Error ? err.message : 'Failed to download gradebooks';
			toast.error(downloadError);
			console.error('Gradebook download error:', err);
			console.error('Full error object:', err);
		}
	}

	async function downloadSingleGradebook(course: Course) {
		downloadingGradebooks = true;
		downloadError = null;
		downloadCount = 1;

		try {
			console.log(`Downloading gradebook for: ${course.name}`);

			// Call API to download gradebook (returns CSV blob)
			const csvBlob = await downloadGradebook(course.course_id, course.name, course.url);

			console.log('Received CSV blob:', csvBlob.type, csvBlob.size, 'bytes');

			// Create a safe filename
			const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
			const safeName = course.name.replace(/[^a-z0-9]/gi, '-').toLowerCase();
			const filename = `${safeName}_${timestamp}.csv`;

			// Create download link and trigger download
			const url = window.URL.createObjectURL(csvBlob);
			const a = document.createElement('a');
			a.href = url;
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			window.URL.revokeObjectURL(url);

			console.log('Download triggered successfully');

			// Close modal after successful download
			downloadingGradebooks = false;

			toast.success(`Successfully downloaded gradebook for ${course.name}`);
		} catch (err) {
			downloadError = err instanceof Error ? err.message : 'Failed to download gradebook';
			toast.error(downloadError);
			console.error('Gradebook download error:', err);
		}
	}
</script>

{#if $user}
	<div class="mx-auto max-w-7xl">
		<!-- Header with Background Illustration -->
		<div class="relative mb-6 overflow-hidden rounded-2xl shadow-lg">
			<!-- Background Image -->
			<div class="absolute inset-0">
				<img
					src={intersight}
					alt=""
					class="h-full w-full object-cover opacity-30 dark:opacity-20"
				/>
				<!-- Gradient Overlay for better text readability -->
				<div
					class="absolute inset-0 bg-linear-to-br from-cisco-blue-05/90 to-cisco-light-blue-05/90 dark:from-cisco-gray-80/95 dark:to-cisco-gray-70/95"
				></div>
			</div>

			<!-- Content with Skewed Backgrounds -->
			<div class="relative z-10 p-8">
				<div class="flex flex-col items-start gap-3 md:flex-row md:items-center md:justify-between">
					<!-- Title with Skewed Background -->
					<div class="relative inline-block">
						<div
							class="absolute inset-0 -right-4 -left-4 bg-cisco-primary-blue opacity-90 dark:bg-cisco-blue-60"
							style="transform: skewX(-7deg); border-radius: 0.5rem;"
						></div>
						<div class="relative px-6 py-3">
							<span class="font-cisco-thin font-bold text-white"> NetAcad Gradebook Manager </span>
						</div>
					</div>

					<!-- Subtitle with Skewed Background -->
					<div class="relative inline-block">
						<!-- <div
						class="absolute inset-0 -right-4 -left-4 bg-cisco-light-blue-50 opacity-90 dark:bg-cisco-gray-60"
						style="transform: skewX(-7deg); border-radius: 0.5rem;"
					></div> -->
						<div class="relative px-6 py-2">
							<p class="font-cisco-thin font-semibold text-cisco-gray-70 dark:text-cisco-gray-05">
								Manage & sync courses with ease
							</p>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Actions Bar -->
		<div
			class="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-lg bg-white p-4 shadow dark:border dark:border-cisco-gray-70 dark:bg-cisco-gray-90"
		>
			<!-- Left side: Actions Dropdown -->
			<div class="flex items-center gap-3">
				<Dropdown bind:show={showActionsDropdown} side="bottom" align="start">
					{#snippet trigger()}
						<button
							class="flex items-center gap-2 rounded-full bg-cisco-blue-50 px-4 py-2 font-medium text-white shadow transition hover:bg-cisco-blue-60"
						>
							<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M4 6h16M4 12h16M4 18h16"
								></path>
							</svg>
							Actions
							<svg
								class="h-4 w-4 transition-transform {showActionsDropdown ? 'rotate-180' : ''}"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M19 9l-7 7-7-7"
								></path>
							</svg>
						</button>
					{/snippet}

					{#snippet content()}
						<!-- Sync Courses -->
						<button
							onclick={() => {
								handleSync();
								showActionsDropdown = false;
							}}
							disabled={syncing}
							class="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium text-cisco-gray-80 transition hover:bg-cisco-blue-05 hover:text-cisco-primary-blue disabled:cursor-not-allowed disabled:opacity-50 dark:text-cisco-gray-10 dark:hover:bg-cisco-gray-70 dark:hover:text-cisco-light-blue-50"
						>
							{#if syncing}
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
								<span>Syncing...</span>
							{:else}
								<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
									></path>
								</svg>
								<span>Sync Courses</span>
							{/if}
						</button>

						<!-- Upload File -->
						<Tooltip content="Not implemented yet">
							<button
								onclick={() => {
									fileInput?.click();
									showActionsDropdown = false;
								}}
								class="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium text-cisco-gray-80 transition hover:bg-cisco-blue-05 hover:text-cisco-primary-blue dark:text-cisco-gray-10 dark:hover:bg-cisco-gray-70 dark:hover:text-cisco-light-blue-50"
							>
								<FileArrowUp classname="size-5" />
								<span>Upload File</span>
							</button>
						</Tooltip>

						<!-- Divider -->
						<div class="my-1 h-px bg-cisco-gray-15"></div>

						<!-- Selection Mode Toggle -->
						<button
							onclick={() => {
								toggleSelectionMode();
								showActionsDropdown = false;
							}}
							class="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition {selectionMode
								? 'bg-cisco-blue-05 text-cisco-primary-blue dark:bg-cisco-gray-70 dark:text-cisco-light-blue-50'
								: 'text-cisco-gray-80 hover:bg-cisco-blue-05 hover:text-cisco-primary-blue dark:text-cisco-gray-10 dark:hover:bg-cisco-gray-70 dark:hover:text-cisco-light-blue-50'}"
						>
							<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
								></path>
							</svg>
							<span>{selectionMode ? 'Cancel Select' : 'Select Courses'}</span>
							{#if selectionMode}
								<span class="ml-auto text-xs text-cisco-primary-blue">Active</span>
							{/if}
						</button>
					{/snippet}
				</Dropdown>

				<!-- Hidden File Input -->
				<input
					bind:this={fileInput}
					bind:files
					type="file"
					accept=".csv,.txt,.json"
					onchange={handleFileSelect}
					class="hidden"
					id="file-upload"
				/>

				<!-- File Upload Badge (shown when file is selected) -->
				{#if uploadedFile}
					<div
						class="flex items-center gap-2 rounded-lg bg-cisco-light-blue-05 px-3 py-2 text-sm text-cisco-gray-80 dark:bg-cisco-gray-70 dark:text-cisco-gray-10"
					>
						<svg
							class="h-4 w-4 text-cisco-primary-blue"
							fill="currentColor"
							viewBox="0 0 20 20"
							xmlns="http://www.w3.org/2000/svg"
						>
							<path
								fill-rule="evenodd"
								d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
								clip-rule="evenodd"
							></path>
						</svg>
						<span class="font-medium">{uploadedFile.name}</span>
						<button
							onclick={clearFile}
							aria-label="Remove selected file"
							class="ml-2 text-cisco-gray-60 hover:text-cisco-accent-magenta"
						>
							<svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
								<path
									fill-rule="evenodd"
									d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
									clip-rule="evenodd"
								></path>
							</svg>
						</button>
					</div>
				{/if}
			</div>

			<!-- Right side: Search and Sort -->
			<div class="flex items-center gap-3">
				<div class="relative">
					<input
						type="text"
						bind:value={searchQuery}
						placeholder="Search courses..."
						class="rounded-full border border-cisco-gray-20 px-4 py-2 pr-10 focus:border-cisco-primary-blue focus:ring focus:ring-cisco-primary-blue/20 focus:outline-none dark:border-cisco-gray-60 dark:bg-cisco-gray-80 dark:text-cisco-gray-10 dark:placeholder-cisco-gray-40"
						name="search"
					/>
					{#if searchQuery}
						<button
							onclick={() => (searchQuery = '')}
							class="absolute top-1/2 right-3 -translate-y-1/2 text-cisco-gray-50 transition hover:text-cisco-gray-80 dark:text-cisco-gray-40 dark:hover:text-cisco-gray-10"
							aria-label="Clear search"
						>
							<X classname="h-4 w-4" />
						</button>
					{/if}
				</div>
				<div class="relative">
					<select
						name="sort"
						bind:value={sortOption}
						class="min-w-60 appearance-none rounded-full border border-cisco-gray-20 bg-white py-2 pr-10 pl-10 focus:border-cisco-primary-blue focus:ring-2 focus:ring-cisco-primary-blue/20 focus:outline-none dark:border-cisco-gray-60 dark:bg-cisco-gray-80 dark:text-cisco-gray-10"
					>
						<option value="name-asc">Course Number (Low to High)</option>
						<option value="name-desc">Course Number (High to Low)</option>
						<option value="start-date-desc">Start Date (Newest First)</option>
						<option value="start-date-asc">Start Date (Oldest First)</option>
						<option value="end-date-desc">End Date (Newest First)</option>
						<option value="end-date-asc">End Date (Oldest First)</option>
						<option value="created-desc">Date Added (Newest First)</option>
						<option value="created-asc">Date Added (Oldest First)</option>
					</select>
					<!-- Sort Icon -->
					<svg
						class="pointer-events-none absolute top-1/2 left-3 h-5 w-5 -translate-y-1/2 text-cisco-gray-50 dark:text-cisco-gray-40"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3 7.5L7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5"
						/>
					</svg>
					<!-- Dropdown Arrow -->
					<svg
						class="pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-cisco-gray-50 dark:text-cisco-gray-40"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M19 9l-7 7-7-7"
						/>
					</svg>
				</div>
			</div>
		</div>

		<!-- Sync Status Indicator -->
		{#if showSyncStatus && currentSyncId}
			<div class="mb-6">
				<SyncStatusIndicator
					syncId={currentSyncId}
					onComplete={handleSyncComplete}
					onError={handleSyncError}
				/>
			</div>
		{/if}

		<!-- Courses Grid -->
		{#if loading}
			<div class="flex h-64 items-center justify-center">
				<div class="flex flex-col items-center gap-4">
					<svg
						class="h-12 w-12 animate-spin text-cisco-primary-blue"
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
					<p class="text-cisco-gray-60 dark:text-cisco-gray-40">Loading courses...</p>
				</div>
			</div>
		{:else if filteredCourses.length === 0}
			<div
				class="rounded-lg border-2 border-dashed border-cisco-gray-20 bg-white p-12 text-center dark:border-cisco-gray-60 dark:bg-cisco-gray-90"
			>
				<svg
					class="mx-auto mb-4 h-16 w-16 text-cisco-gray-30 dark:text-cisco-gray-50"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
					></path>
				</svg>
				<h3 class="mb-2 text-xl font-semibold text-cisco-gray-80 dark:text-cisco-gray-10">
					No Courses Found
				</h3>
				<p class="mb-4 text-cisco-gray-60 dark:text-cisco-gray-30">
					{searchQuery
						? 'Try adjusting your search or filters'
						: 'Click "Sync Courses" to fetch courses from NetAcad'}
				</p>
			</div>
		{:else}
			<!-- Select All Bar (shown in selection mode) -->
			{#if selectionMode && filteredCourses.length > 0}
				<div
					class="mb-4 rounded-lg bg-cisco-blue-05 p-3 dark:border dark:border-cisco-gray-60 dark:bg-cisco-gray-80"
				>
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-3">
							<input
								type="checkbox"
								checked={allVisibleSelected}
								onchange={toggleSelectAll}
								class="h-4 w-4 cursor-pointer rounded border-cisco-gray-30 text-cisco-primary-blue focus:ring-2 focus:ring-cisco-primary-blue dark:border-cisco-gray-50 dark:bg-cisco-gray-70"
								aria-label="Select all visible courses"
							/>
							<span class="text-sm font-medium text-cisco-gray-80 dark:text-cisco-gray-10">
								{allVisibleSelected ? 'Deselect All' : 'Select All'} on this page ({filteredCourses.length}
								courses)
							</span>
						</div>
						{#if selectedCount > 0}
							<span
								class="text-sm font-semibold text-cisco-primary-blue dark:text-cisco-light-blue-50"
							>
								{selectedCount} selected
							</span>
						{/if}
					</div>

					<!-- Select All Pages Banner (shown when user has selected all visible) -->
					{#if allVisibleSelected && !selectAllPages && totalCourses > filteredCourses.length}
						<div
							class="mt-2 flex items-center justify-between rounded border border-cisco-primary-blue/30 bg-cisco-blue-10 p-2 dark:border-cisco-light-blue-50/30 dark:bg-cisco-gray-70"
						>
							<span class="text-sm text-cisco-gray-80 dark:text-cisco-gray-10">
								All {filteredCourses.length} courses on this page are selected.
							</span>
							<button
								onclick={selectAllCourses}
								class="text-sm font-semibold text-cisco-primary-blue hover:underline dark:text-cisco-light-blue-50"
								disabled={loading}
							>
								Select all {totalCourses} courses
							</button>
						</div>
					{/if}

					<!-- All Pages Selected Banner -->
					{#if selectAllPages}
						<div
							class="mt-2 flex items-center justify-between rounded bg-cisco-primary-blue/10 p-2 dark:border dark:border-cisco-light-blue-50/30 dark:bg-cisco-gray-70"
						>
							<div class="flex items-center gap-2">
								<svg
									class="h-5 w-5 text-cisco-primary-blue dark:text-cisco-light-blue-50"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
									></path>
								</svg>
								<span
									class="text-sm font-medium text-cisco-primary-blue dark:text-cisco-light-blue-50"
								>
									All {totalCourses} courses are selected
								</span>
							</div>
							<button
								onclick={clearSelection}
								class="text-sm font-medium text-cisco-gray-60 hover:text-cisco-gray-80 dark:text-cisco-gray-30 dark:hover:text-cisco-gray-10"
							>
								Clear selection
							</button>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Course Cards -->
			<div>
				<Courses
					courses={filteredCourses}
					{selectionMode}
					{selectedCourseIds}
					{toggleCourseSelection}
					{downloadSingleGradebook}
				/>
			</div>

			<!-- Pagination -->
			<div class="p-4 shadow dark:border dark:border-cisco-gray-60 dark:bg-cisco-gray-80">
				<Pagination count={totalCourses} perPage={pageSize} {currentPage} onPageChange={goToPage} />
			</div>
		{/if}

		<!-- Floating Action Bar (shown when courses are selected) -->
		{#if selectedCount > 0}
			<FloatingActionBar {selectedCount} {downloadGradebooks} {clearSelection} />
		{/if}

		<!-- Download Modal -->
		<DownloadGradebookModal
			bind:show={downloadingGradebooks}
			bind:downloadError
			bind:downloadCount
		/>
	</div>
{:else}
	<!-- User not authenticated - should not reach here due to layout guard, but extra safety -->
	<div class="flex h-64 items-center justify-center">
		<div class="flex flex-col items-center gap-4">
			<svg
				class="h-12 w-12 text-cisco-gray-40"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
				></path>
			</svg>
			<p class="text-cisco-gray-60 dark:text-cisco-gray-40">
				Authentication required to view courses
			</p>
		</div>
	</div>
{/if}
