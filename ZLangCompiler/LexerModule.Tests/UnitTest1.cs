namespace LexerModule.Tests;

[TestFixture]
public class Tests
{

    [Test]
    public void TestModuleAssignment()
    {
        const string input = "module string = std.string;";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordModule, "module", 1, 1),
            new Token(TokenKind.Identifier, "string", 1, 8),
            new Token(TokenKind.SymbolEquals, "=", 1, 15),
            new Token(TokenKind.Identifier, "std", 1, 17),
            new Token(TokenKind.SymbolDot, ".", 1, 20),
            new Token(TokenKind.Identifier, "string", 1, 21),
            new Token(TokenKind.SymbolSemicolon, ";", 1, 27),
            new Token(TokenKind.Eof, string.Empty, 1, 28)
        }));
    }
    
    [Test]
    public void TestStructAssignment()
    {
        const string input = "struct HeapAllocator = std.mem.heap.Allocator;";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordStruct, "struct", 1, 1),
            new Token(TokenKind.Identifier, "HeapAllocator", 1, 8),
            new Token(TokenKind.SymbolEquals, "=", 1, 22),
            new Token(TokenKind.Identifier, "std", 1, 24),
            new Token(TokenKind.SymbolDot, ".", 1, 27),
            new Token(TokenKind.Identifier, "mem", 1, 28),
            new Token(TokenKind.SymbolDot, ".", 1, 31),
            new Token(TokenKind.Identifier, "heap", 1, 32),
            new Token(TokenKind.SymbolDot, ".", 1, 36),
            new Token(TokenKind.Identifier, "Allocator", 1, 37),
            new Token(TokenKind.SymbolSemicolon, ";", 1, 46),
            new Token(TokenKind.Eof, string.Empty, 1, 47)
        }));
    }
    
    [Test]
    public void TestGenericStructAssignment()
    {
        const string input = "struct Array<T> = array.Array<T>;";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordStruct, "struct", 1, 1),
            new Token(TokenKind.Identifier, "Array", 1, 8),
            new Token(TokenKind.SymbolLessThan, "<", 1, 13),
            new Token(TokenKind.Identifier, "T", 1, 14),
            new Token(TokenKind.SymbolGreaterThan, ">", 1, 15),
            new Token(TokenKind.SymbolEquals, "=", 1, 17),
            new Token(TokenKind.Identifier, "array", 1, 19),
            new Token(TokenKind.SymbolDot, ".", 1, 24),
            new Token(TokenKind.Identifier, "Array", 1, 25),
            new Token(TokenKind.SymbolLessThan, "<", 1, 30),
            new Token(TokenKind.Identifier, "T", 1, 31),
            new Token(TokenKind.SymbolGreaterThan, ">", 1, 32),
            new Token(TokenKind.SymbolSemicolon, ";", 1, 33),
            new Token(TokenKind.Eof, string.Empty, 1, 34)
        }));
    }
}