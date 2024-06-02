export interface IProductParams { 
    category?: string | null;
    searchTerm?: string | null;
}

export default async function getProducts(params: IProductParams) {
    try {
        const {category, searchTerm} = params;
        
        let searchString = searchTerm;

        if (!searchTerm) {
            searchString = ''
        }

        let query: any = {}

        if (category) {
            query.category = category
        }

        const response = await fetch() 
    } catch (error: any) {
        throw new Error(error)
    }
}