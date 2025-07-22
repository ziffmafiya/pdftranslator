import express from 'express';
import multer from 'multer';
import * as deepl from 'deepl-node';
import path from 'path';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import fs from 'fs';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = 3000;

// Ensure directories exist
const uploadDir = path.join(__dirname, 'uploads');
const downloadDir = path.join(__dirname, 'downloads');
fs.mkdirSync(uploadDir, { recursive: true });
fs.mkdirSync(downloadDir, { recursive: true });

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        cb(null, Date.now() + '-' + file.originalname);
    }
});

const upload = multer({ storage: storage });

const authKey = process.env.DEEPL_API_KEY;
if (!authKey) {
    throw new Error('Переменная окружения DEEPL_API_KEY не задана');
}
const translator = new deepl.Translator(authKey);

app.use(express.static(path.join(__dirname, 'public')));
app.use('/downloads', express.static(downloadDir));


app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'templates', 'index.html'));
});

app.post('/translate', upload.single('file'), async (req, res) => {
    if (!req.file) {
        return res.status(400).send('No file uploaded.');
    }

    const inputPath = req.file.path;
    const targetLang = req.body.language;
    const outputFilename = `translated-${req.file.filename}`;
    const outputPath = path.join(downloadDir, outputFilename);

    if (!targetLang) {
        return res.status(400).send('No target language selected.');
    }

    try {
        await translator.translateDocument(
            inputPath,
            outputPath,
            null, // Source lang, null for auto-detect
            targetLang
        );
        res.redirect(`/downloads/${outputFilename}`);
    } catch (error) {
        console.error(error);
        let errorMessage = 'An error occurred during translation.';
        if (error.documentHandle) {
            errorMessage = `Error after document upload. ID: ${error.documentHandle.documentId}, Key: ${error.documentHandle.documentKey}`;
        }
        res.status(500).send(errorMessage);
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
