# PDF-переводчик на Python и Flask

Это простое веб-приложение, которое позволяет загружать PDF-файлы, переводить их с помощью различных API и скачивать переведенную версию.

## Особенности

-   Простой веб-интерфейс для загрузки файлов.
-   Выбор между DeepL, Google Translate, ApyHub Translate Documents и LibreTranslate.
-   Серверная часть на Python и Flask, готовая к развертыванию на Vercel.

## Поддерживаемые движки перевода и их особенности

*   **DeepL**:
    *   Официальная поддержка перевода документов с сохранением верстки.
    *   Требует `DEEPL_API_KEY`.
*   **Google Translate**:
    *   **Внимание:** Интеграция Google Translate для *документов* (PDF) значительно сложнее, чем для DeepL. Она требует настройки Google Cloud Platform, создания проекта, включения API Document Translation, настройки учетных данных (Service Account) и использования Google Cloud Storage для временного хранения файлов. В текущей реализации Google Translate API для документов **не реализован**, и при его выборе будет выдана ошибка `NotImplementedError`. Если вам нужна эта функциональность, потребуется дополнительная работа по настройке Google Cloud.
    *   Требует `GOOGLE_CLOUD_PROJECT_ID` и настроенных учетных данных Google Cloud.
*   **ApyHub Translate Documents**:
    *   Поддерживает перевод документов с сохранением верстки.
    *   Требует `APYHUB_API_KEY`.
*   **LibreTranslate**:
    *   **Внимание:** LibreTranslate — это в основном API для перевода *текста*. Для сохранения верстки PDF с LibreTranslate приложение использует сложную логику извлечения текста из PDF и его повторной вставки. Это может привести к проблемам с форматированием и наложением текста, особенно для сложных документов.
    *   Требует `LIBRETRANSLATE_API_URL` (может быть локальный сервер или публичный инстанс).

## Требования

-   [Python](https://www.python.org/) (версия 3.8 или выше)
-   API-ключи для выбранных сервисов:
    *   [DeepL API Key](https://www.deepl.com/pro-api)
    *   [Google Cloud Project ID](https://cloud.google.com/resource-manager/docs/creating-managing-projects) и настроенные [учетные данные Google Cloud](https://cloud.google.com/docs/authentication/getting-started)
    *   [ApyHub API Key](https://apyhub.com/)
    *   URL для [LibreTranslate API](https://libretranslate.com/) (если используете свой сервер LibreTranslate)

## Установка и запуск LibreTranslate (локально)

Если вы планируете использовать LibreTranslate, вам нужно запустить его локально.

1.  **Скачайте LibreTranslate:**
    Перейдите на страницу [релизов LibreTranslate на GitHub](https://github.com/LibreTranslate/LibreTranslate/releases) и скачайте последнюю версию.

2.  **Запустите LibreTranslate:**
    Следуйте инструкциям на странице LibreTranslate для запуска сервера. Обычно это делается с помощью Docker или прямого запуска Python-скрипта. Например, с Docker:
    ```bash
    docker run -ti --rm -p 5000:5000 libretranslate/libretranslate
    ```
    Убедитесь, что LibreTranslate запущен и доступен по адресу, который вы укажете в `LIBRETRANSLATE_API_URL`.

## Установка и запуск PDF-переводчика (локально)

1.  **Клонируйте репозиторий или скачайте файлы проекта.**

2.  **Создайте и активируйте виртуальное окружение (рекомендуется):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Для Windows: venv\Scripts\activate
    ```

3.  **Установите зависимости:**
    Откройте терминал в папке проекта и выполните команду:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Настройте переменные окружения:**
    -   Создайте файл с именем `.env` в корневой папке проекта.
    -   Добавьте в него ваши API-ключи и ID проекта Google Cloud в следующем формате:
        ```
        DEEPL_API_KEY="ваш_секретный_ключ_от_deepl"
        GOOGLE_CLOUD_PROJECT_ID="ваш_id_проекта_google_cloud"
        APYHUB_API_KEY="ваш_ключ_от_apyhub"
        LIBRETRANSLATE_API_URL="http://localhost:5000/translate" # Или ваш URL
        ```
    -   **Для Google Translate (локально):** Убедитесь, что у вас настроены учетные данные Google Cloud. Самый простой способ — это установить переменную окружения `GOOGLE_APPLICATION_CREDENTIALS`, указывающую на файл JSON с ключом сервисного аккаунта.
    -   **Для LibreTranslate (локально):** Убедитесь, что ваш локальный сервер LibreTranslate запущен и переменная `LIBRETRANSLATE_API_URL` в `.env` указывает на него (например, `http://localhost:5000`).

5.  **Запустите сервер PDF-переводчика:**
    ```bash
    python app.py
    ```
    Сервер будет запущен, и в консоли вы увидите сообщение о том, что он работает по адресу [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Использование

1.  Откройте в браузере адрес [http://localhost:5000](http://localhost:5000).
2.  Нажмите на кнопку выбора файла и загрузите ваш PDF-документ.
3.  **Выберите движок перевода**: DeepL, Google Translate, ApyHub или LibreTranslate.
4.  Выберите язык, на который нужно перевести документ (Русский или Украинский).
5.  Нажмите кнопку "Translate".
6.  После завершения перевода браузер автоматически скачает переведенный PDF-файл.

## Развертывание на Vercel

Этот проект настроен для легкого развертывания на Vercel.

1.  **Загрузите проект на GitHub.** Убедитесь, что файлы `.env` и `venv/` добавлены в `.gitignore`.
2.  **Зарегистрируйтесь на Vercel**, используя ваш GitHub-аккаунт.
3.  **Импортируйте репозиторий** в Vercel. Платформа автоматически определит настройки из файла `vercel.json`.
4.  **Настройте переменные окружения** в дашборде вашего проекта на Vercel. Создайте переменные `DEEPL_API_KEY`, `GOOGLE_CLOUD_PROJECT_ID`, `APYHUB_API_KEY` и `LIBRETRANSLATE_API_URL` и укажите в них ваши ключи/ID/URL.
5.  **Нажмите "Deploy"**. После завершения процесса ваше приложение будет доступно по публичной ссылке.
