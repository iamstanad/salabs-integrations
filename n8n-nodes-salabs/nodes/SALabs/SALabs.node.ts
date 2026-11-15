import type {
	IDataObject,
	IExecuteFunctions,
	IHttpRequestMethods,
	IHttpRequestOptions,
	ILoadOptionsFunctions,
	INodeExecutionData,
	INodePropertyOptions,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeApiError, NodeConnectionTypes, NodeOperationError, sleep } from 'n8n-workflow';

const CRED = 'saLabsApi';

type Ctx = IExecuteFunctions | ILoadOptionsFunctions;

async function baseUrl(ctx: Ctx): Promise<string> {
	const creds = await ctx.getCredentials(CRED);
	return String(creds.baseUrl || 'http://localhost:8000').replace(/\/+$/, '');
}

async function api(
	ctx: Ctx,
	method: IHttpRequestMethods,
	path: string,
	extra: Partial<IHttpRequestOptions> = {},
): Promise<{ status: number; body: any; headers: IDataObject }> {
	const options: IHttpRequestOptions = {
		method,
		url: (await baseUrl(ctx)) + path,
		json: true,
		returnFullResponse: true,
		ignoreHttpStatusErrors: true,
		timeout: 300000,
		...extra,
	};
	const res = await ctx.helpers.httpRequestWithAuthentication.call(ctx, CRED, options);
	const status = res.statusCode as number;
	let body = res.body;
	if (Buffer.isBuffer(body) && extra.encoding !== 'arraybuffer') {
		try {
			body = JSON.parse(body.toString('utf8'));
		} catch {
			/* not JSON */
		}
	}
	if (status >= 400) {
		const err = body?.error ?? {};
		const message = err.message ? `${err.message} (${err.code})` : `HTTP ${status}`;
		throw new NodeApiError(ctx.getNode(), { message, code: err.code } as any, {
			message,
			httpCode: String(status),
		});
	}
	return { status, body, headers: res.headers ?? {} };
}

/** Poll a job until it finishes (long transcriptions/voiceovers). */
async function waitForJob(ctx: IExecuteFunctions, job: IDataObject, maxMinutes = 60) {
	let delay = 2000;
	const deadline = Date.now() + maxMinutes * 60000;
	while (job.status !== 'succeeded' && job.status !== 'failed') {
		if (Date.now() > deadline) {
			throw new NodeOperationError(ctx.getNode(), `Job ${job.id} is still running.`);
		}
		await sleep(delay);
		delay = Math.min(delay * 1.5, 10000);
		job = (await api(ctx, 'GET', `/v1/jobs/${job.id}`)).body;
	}
	if (job.status === 'failed') {
		throw new NodeOperationError(ctx.getNode(), `Job failed: ${job.error}`);
	}
	return job;
}

async function downloadFile(ctx: IExecuteFunctions, fileId: string): Promise<Buffer> {
	const res = await api(ctx, 'GET', `/v1/files/${fileId}/content`, {
		encoding: 'arraybuffer',
		json: false,
	});
	return Buffer.from(res.body);
}

export class SALabs implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'S.A Labs',
		name: 'saLabs',
		icon: { light: 'file:salabs.svg', dark: 'file:salabs.dark.svg' },
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
		description: 'Scrape web pages, generate speech and transcribe audio/video with S.A Labs',
		defaults: { name: 'S.A Labs' },
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		usableAsTool: true,
		credentials: [{ name: CRED, required: true }],
		properties: [
			{
				displayName: 'Resource',
				name: 'resource',
				type: 'options',
				noDataExpression: true,
				options: [
					{ name: 'Web Page', value: 'web' },
					{ name: 'Speech', value: 'speech' },
					{ name: 'Transcription', value: 'transcription' },
					{ name: 'Account', value: 'account' },
				],
				default: 'web',
			},

			// ---- Account ----
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['account'] } },
				options: [
					{
						name: 'Get Balance',
						value: 'get',
						action: 'Get credit balance',
						description: 'Credits left, spend this month and monthly cap',
					},
				],
				default: 'get',
			},

			// ---- Web page ----
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['web'] } },
				options: [
					{
						name: 'Scrape',
						value: 'scrape',
						action: 'Scrape a web page',
						description: 'Get a web page as clean Markdown, text, HTML or links',
					},
				],
				default: 'scrape',
			},
			{
				displayName: 'URL',
				name: 'url',
				type: 'string',
				required: true,
				default: '',
				placeholder: 'https://example.com/article',
				displayOptions: { show: { resource: ['web'], operation: ['scrape'] } },
			},
			{
				displayName: 'Formats',
				name: 'formats',
				type: 'multiOptions',
				options: [
					{ name: 'Markdown', value: 'markdown' },
					{ name: 'Plain Text', value: 'text' },
					{ name: 'HTML (Cleaned)', value: 'html' },
					{ name: 'Raw HTML', value: 'rawHtml' },
					{ name: 'Links', value: 'links' },
				],
				default: ['markdown'],
				displayOptions: { show: { resource: ['web'], operation: ['scrape'] } },
			},
			{
				displayName: 'Options',
				name: 'scrapeOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: { show: { resource: ['web'], operation: ['scrape'] } },
				options: [
					{
						displayName: 'Only Main Content',
						name: 'onlyMainContent',
						type: 'boolean',
						default: true,
						description: 'Whether to drop menus, footers and sidebars',
					},
					{
						displayName: 'Render JavaScript',
						name: 'render',
						type: 'options',
						options: [
							{ name: 'Auto', value: 'auto' },
							{ name: 'Always', value: 'always' },
							{ name: 'Never', value: 'never' },
						],
						default: 'auto',
						description: 'Whether to load the page in a real browser',
					},
					{
						displayName: 'Wait For (Ms)',
						name: 'waitFor',
						type: 'number',
						default: 0,
						description: 'Extra time to wait for the page to load (browser mode)',
					},
				],
			},

			// ---- Speech ----
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['speech'] } },
				options: [
					{
						name: 'Generate',
						value: 'generate',
						action: 'Generate speech from text',
						description: 'Turn text into an audio file',
					},
					{
						name: 'List Voices',
						value: 'voices',
						action: 'List voices',
						description: 'List all available voices',
					},
				],
				default: 'generate',
			},
			{
				displayName: 'Text',
				name: 'text',
				type: 'string',
				typeOptions: { rows: 4 },
				required: true,
				default: '',
				description: 'What to say (up to 100,000 characters)',
				displayOptions: { show: { resource: ['speech'], operation: ['generate'] } },
			},
			{
				displayName: 'Voice Name or ID',
				name: 'voice',
				type: 'options',
				typeOptions: { loadOptionsMethod: 'getVoices' },
				default: 'af_heart',
				description:
					'Choose from the list, or specify an ID using an <a href="https://docs.n8n.io/code/expressions/">expression</a>',
				displayOptions: { show: { resource: ['speech'], operation: ['generate'] } },
			},
			{
				displayName: 'Output',
				name: 'speechOutput',
				type: 'options',
				options: [
					{ name: 'Audio File (Binary)', value: 'binary' },
					{ name: 'Download Link Only', value: 'url' },
				],
				default: 'binary',
				displayOptions: { show: { resource: ['speech'], operation: ['generate'] } },
			},
			{
				displayName: 'Put Output File in Field',
				name: 'binaryPropertyOutput',
				type: 'string',
				default: 'data',
				displayOptions: {
					show: { resource: ['speech'], operation: ['generate'], speechOutput: ['binary'] },
				},
			},
			{
				displayName: 'Options',
				name: 'speechOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: { show: { resource: ['speech'], operation: ['generate'] } },
				options: [
					{
						displayName: 'Format',
						name: 'format',
						type: 'options',
						options: [
							{ name: 'MP3', value: 'mp3' },
							{ name: 'WAV', value: 'wav' },
							{ name: 'Opus', value: 'opus' },
							{ name: 'AAC', value: 'aac' },
							{ name: 'FLAC', value: 'flac' },
						],
						default: 'mp3',
					},
					{
						displayName: 'Speed',
						name: 'speed',
						type: 'number',
						typeOptions: { minValue: 0.5, maxValue: 2, numberPrecision: 2 },
						default: 1,
					},
					{
						displayName: 'File Name',
						name: 'fileName',
						type: 'string',
						default: '',
						placeholder: 'voiceover.mp3',
					},
				],
			},

			// ---- Transcription ----
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['transcription'] } },
				options: [
					{
						name: 'Transcribe',
						value: 'transcribe',
						action: 'Transcribe audio or video',
						description: 'Get text, timestamps and SRT/VTT subtitles',
					},
				],
				default: 'transcribe',
			},
			{
				displayName: 'Input',
				name: 'source',
				type: 'options',
				options: [
					{ name: 'File From Previous Node (Binary)', value: 'binary' },
					{ name: 'Link to a Media File', value: 'url' },
				],
				default: 'binary',
				displayOptions: { show: { resource: ['transcription'] } },
			},
			{
				displayName: 'Input Binary Field',
				name: 'binaryPropertyName',
				type: 'string',
				default: 'data',
				required: true,
				hint: 'The name of the input field containing the audio/video file',
				displayOptions: { show: { resource: ['transcription'], source: ['binary'] } },
			},
			{
				displayName: 'Media URL',
				name: 'mediaUrl',
				type: 'string',
				default: '',
				required: true,
				placeholder: 'https://example.com/podcast.mp3',
				description: 'Direct link to an audio/video file (YouTube links are not supported)',
				displayOptions: { show: { resource: ['transcription'], source: ['url'] } },
			},
			{
				displayName: 'Model',
				name: 'model',
				type: 'options',
				options: [
					{ name: 'Accurate', value: 'accurate', description: '20 credits per minute' },
					{ name: 'Fast', value: 'fast', description: '15 credits per minute' },
				],
				default: 'accurate',
				displayOptions: { show: { resource: ['transcription'] } },
			},
			{
				displayName: 'Options',
				name: 'transcribeOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: { show: { resource: ['transcription'] } },
				options: [
					{
						displayName: 'Language',
						name: 'language',
						type: 'string',
						default: '',
						placeholder: 'en',
						description: 'Spoken language code. Leave empty to auto-detect.',
					},
					{
						displayName: 'Translate to English',
						name: 'translate',
						type: 'boolean',
						default: false,
					},
					{
						displayName: 'Word Timestamps',
						name: 'wordTimestamps',
						type: 'boolean',
						default: false,
					},
					{
						displayName: 'Attach Subtitle File',
						name: 'attachSubtitles',
						type: 'options',
						options: [
							{ name: 'None', value: 'none' },
							{ name: 'SRT', value: 'srt' },
							{ name: 'VTT', value: 'vtt' },
							{ name: 'Both', value: 'both' },
						],
						default: 'none',
						description: 'Whether to add the subtitles as binary files (to save or upload)',
					},
				],
			},
		],
	};

	methods = {
		loadOptions: {
			async getVoices(this: ILoadOptionsFunctions): Promise<INodePropertyOptions[]> {
				const { body } = await api(this, 'GET', '/v1/tts/voices');
				return (body.data as IDataObject[]).map((v) => ({
					name: `${v.name} (${v.language_name}, ${v.gender})`,
					value: v.id as string,
				}));
			},
		},
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const out: INodeExecutionData[] = [];

		for (let i = 0; i < items.length; i++) {
			try {
				const resource = this.getNodeParameter('resource', i) as string;
				const operation = this.getNodeParameter('operation', i) as string;

				if (resource === 'web' && operation === 'scrape') {
					const opts = this.getNodeParameter('scrapeOptions', i, {}) as IDataObject;
					const { body } = await api(this, 'POST', '/v1/scrape', {
						body: {
							url: this.getNodeParameter('url', i) as string,
							formats: this.getNodeParameter('formats', i, ['markdown']),
							...opts,
						},
					});
					out.push({
						json: { ...body.data, credits_charged: body.credits_charged },
						pairedItem: { item: i },
					});
				} else if (resource === 'speech' && operation === 'voices') {
					const { body } = await api(this, 'GET', '/v1/tts/voices');
					for (const v of body.data as IDataObject[]) {
						out.push({ json: v, pairedItem: { item: i } });
					}
				} else if (resource === 'speech' && operation === 'generate') {
					const text = this.getNodeParameter('text', i) as string;
					const opts = this.getNodeParameter('speechOptions', i, {}) as IDataObject;
					const reqBody = {
						text,
						voice: this.getNodeParameter('voice', i) as string,
						speed: (opts.speed as number) ?? 1,
						format: (opts.format as string) ?? 'mp3',
					};
					let result: IDataObject;
					let credits: IDataObject[string];
					if (text.length <= 4000) {
						const r = await api(this, 'POST', '/v1/tts', { qs: { output: 'url' }, body: reqBody });
						if (r.status === 202) {
							const job = await waitForJob(this, r.body);
							result = job.result as IDataObject;
							credits = job.credits_charged;
						} else {
							result = r.body;
							credits = r.body.credits_charged;
						}
					} else {
						const r = await api(this, 'POST', '/v1/tts/async', { body: reqBody });
						const job = await waitForJob(this, r.body);
						result = job.result as IDataObject;
						credits = job.credits_charged;
					}
					const json: IDataObject = {
						audio_url: result.audio_url,
						duration_seconds: result.duration_seconds,
						voice: result.voice,
						format: result.format,
						characters: result.characters,
						credits_charged: credits,
					};
					const item: INodeExecutionData = { json, pairedItem: { item: i } };
					if (this.getNodeParameter('speechOutput', i) === 'binary') {
						const file = result.file as IDataObject;
						const buf = await downloadFile(this, file.id as string);
						const prop = this.getNodeParameter('binaryPropertyOutput', i, 'data') as string;
						const name = (opts.fileName as string) || `speech.${reqBody.format}`;
						item.binary = {
							[prop]: await this.helpers.prepareBinaryData(
								buf,
								name,
								file.content_type as string,
							),
						};
					}
					out.push(item);
				} else if (resource === 'transcription' && operation === 'transcribe') {
					const source = this.getNodeParameter('source', i) as string;
					const opts = this.getNodeParameter('transcribeOptions', i, {}) as IDataObject;
					const fields: IDataObject = {
						model: this.getNodeParameter('model', i) as string,
						translate: Boolean(opts.translate),
						word_timestamps: Boolean(opts.wordTimestamps),
						wait: true,
					};
					if (opts.language) fields.language = opts.language;
					let r;
					if (source === 'url') {
						r = await api(this, 'POST', '/v1/transcribe', {
							body: { url: this.getNodeParameter('mediaUrl', i) as string, ...fields },
						});
					} else {
						const prop = this.getNodeParameter('binaryPropertyName', i) as string;
						const bin = this.helpers.assertBinaryData(i, prop);
						const buf = await this.helpers.getBinaryDataBuffer(i, prop);
						const form = new FormData();
						form.append(
							'file',
							new Blob([new Uint8Array(buf)], { type: bin.mimeType || 'application/octet-stream' }),
							bin.fileName || 'media',
						);
						for (const [k, v] of Object.entries(fields)) form.append(k, String(v));
						r = await api(this, 'POST', '/v1/transcribe', { body: form, json: false });
					}
					const job = await waitForJob(this, r.body);
					const res = job.result as IDataObject;
					const item: INodeExecutionData = {
						json: {
							text: res.text,
							language: res.language,
							duration_seconds: res.duration_seconds,
							srt: res.srt,
							vtt: res.vtt,
							segments: res.segments,
							files: res.files,
							credits_charged: job.credits_charged,
						},
						pairedItem: { item: i },
					};
					const attach = (opts.attachSubtitles as string) || 'none';
					if (attach !== 'none') {
						item.binary = {};
						const base = (
							source === 'binary'
								? (this.helpers.assertBinaryData(
										i,
										this.getNodeParameter('binaryPropertyName', i) as string,
									).fileName ?? 'transcript')
								: 'transcript'
						).replace(/\.[^.]+$/, '');
						for (const ext of attach === 'both' ? ['srt', 'vtt'] : [attach]) {
							item.binary[ext] = await this.helpers.prepareBinaryData(
								Buffer.from(String(res[ext] ?? ''), 'utf8'),
								`${base}.${ext}`,
								ext === 'srt' ? 'application/x-subrip' : 'text/vtt',
							);
						}
					}
					out.push(item);
				} else if (resource === 'account') {
					const { body } = await api(this, 'GET', '/v1/account');
					out.push({ json: body, pairedItem: { item: i } });
				} else {
					throw new NodeOperationError(this.getNode(), `Unsupported operation ${operation}`);
				}
			} catch (error) {
				if (this.continueOnFail()) {
					out.push({ json: { error: (error as Error).message }, pairedItem: { item: i } });
					continue;
				}
				// Keeps the S.A Labs error message (e.g. "insufficient_credits") visible in n8n
				throw new NodeOperationError(this.getNode(), error as Error, { itemIndex: i });
			}
		}
		return [out];
	}
}
