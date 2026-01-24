const Simulator = {
    
    // Core logic to generate a single news item
    generateItem: function() {
        const country = this.getRandom(DATA.COUNTRIES);
        const headlineBase = this.generateHeadline();
        const hasError = Math.random() < 0.3; // 30% error rate

        let finalHeadline = headlineBase;
        let errorDetail = null;

        if (hasError) {
            const words = headlineBase.split(' ');
            if (words.length > 0) {
                const idx = Math.floor(Math.random() * words.length);
                const originalWord = words[idx];
                const typos = this.introduceTypo(originalWord);
                
                // If typo actually changed the word
                if (typos !== originalWord) {
                    words[idx] = typos;
                    finalHeadline = words.join(' ');
                    errorDetail = {
                        error_word: typos,
                        corrected_word: originalWord
                    };
                } else {
                    // Failed to make a typo (e.g. word too short), cancel error flag
                    // actually, keep hasError false if no change
                    // hasError = false; 
                }
            }
        }

        return {
            id: Date.now() + Math.random().toString(36).substr(2, 9),
            timestamp: new Date().toISOString(),
            country_name: country.name,
            coordinates: { lat: country.lat, lng: country.lng },
            headline: finalHeadline,
            has_error: !!errorDetail,
            error_detail: errorDetail
        };
    },

    generateHeadline: function() {
        const s = this.getRandom(DATA.HEADLINES.SUBJECTS);
        const v = this.getRandom(DATA.HEADLINES.VERBS);
        const o = this.getRandom(DATA.HEADLINES.OBJECTS);
        return `${s} ${v} ${o}`;
    },

    introduceTypo: function(word) {
        if (word.length < 3) return word;
        
        const type = Math.random();
        const chars = word.split('');
        const idx = Math.floor(Math.random() * chars.length);

        // 1. Swap (33%)
        if (type < 0.33 && idx < chars.length - 1) {
            const temp = chars[idx];
            chars[idx] = chars[idx+1];
            chars[idx+1] = temp;
        }
        // 2. Drop (33%)
        else if (type < 0.66) {
            chars.splice(idx, 1);
        }
        // 3. Adjacency (33%)
        else {
            const char = chars[idx].toLowerCase();
            const adj = DATA.KEYBOARD_ADJACENCY[char];
            if (adj) {
                const replacement = adj[Math.floor(Math.random() * adj.length)];
                chars[idx] = (chars[idx] === chars[idx].toUpperCase()) ? replacement.toUpperCase() : replacement;
            }
        }
        return chars.join('');
    },

    getRandom: function(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }
};
