using System.Diagnostics;

namespace LexerModule.Tests;

[TestFixture]
public class LexerTests
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
            new Token(TokenKind.EOF, string.Empty, 1, 28)
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
            new Token(TokenKind.EOF, string.Empty, 1, 47)
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
            new Token(TokenKind.EOF, string.Empty, 1, 34)
        }));
    }
    
    [Test]
    public void TestVarAssignmentToNumberLiteral()
    {
        const string input = "var number: u32 = 10;";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordVar, "var", 1, 1),
            new Token(TokenKind.Identifier, "number", 1, 5),
            new Token(TokenKind.SymbolColon, ":", 1, 11),
            new Token(TokenKind.Identifier, "u32", 1, 13),
            new Token(TokenKind.SymbolEquals, "=", 1, 17),
            new Token(TokenKind.LiteralInteger, "10", 1, 19),
            new Token(TokenKind.SymbolSemicolon, ";", 1, 21),
            new Token(TokenKind.EOF, string.Empty, 1, 22)
        }));
    }
    
    [Test]
    public void TestVarAssignmentToTextLiteral()
    {
        const string input = "var number = \"Hello World\";";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordVar, "var", 1, 1),
            new Token(TokenKind.Identifier, "number", 1, 5),
            new Token(TokenKind.SymbolEquals, "=", 1, 12),
            new Token(TokenKind.LiteralText, "Hello World", 1, 15),
            new Token(TokenKind.SymbolSemicolon, ";", 1, 27),
            new Token(TokenKind.EOF, string.Empty, 1, 28)
        }));
    }
    
    [Test]
    public void TestTextLiteral()
    {
        const string input = "\"Hello World\"";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.LiteralText, "Hello World", 1, 2),
            new Token(TokenKind.EOF, string.Empty, 1, 14)
        }));
    }
    
    [Test]
    public void TestBoolTrueLiteral()
    {
        const string input = "true";
        var tokens = Lexer.Tokenize(input);
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.LiteralBool, "true", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 5)
        }));
    }
    
    [Test]
    public void TestBoolFalseLiteral()
    {
        const string input = "false";
        var tokens = Lexer.Tokenize(input);
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.LiteralBool, "false", 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, 6)
        }));
    }
    
    [Test]
    public void TestComment()
    {
        const string input = "//Hello Comment";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.EOF, string.Empty, 1, 16)
        }));
    }
    
    [Test]
    public void TestVarAssignmentToStruct()
    {
        const string input = "var v1: Vec2<u8> = { c1 = 0, c2 = 10 }";
        var tokens = Lexer.Tokenize(input);
        
        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(TokenKind.KeywordVar, "var", 1, 1),
            new Token(TokenKind.Identifier, "v1", 1, 5),
            new Token(TokenKind.SymbolColon, ":", 1, 7),
            new Token(TokenKind.Identifier, "Vec2", 1, 9),
            new Token(TokenKind.SymbolLessThan, "<", 1, 13),
            new Token(TokenKind.Identifier, "u8", 1, 14),
            new Token(TokenKind.SymbolGreaterThan, ">", 1, 16),
            new Token(TokenKind.SymbolEquals, "=", 1, 18),
            new Token(TokenKind.SymbolLeftCurlyBrace, "{", 1, 20),
            new Token(TokenKind.Identifier, "c1", 1, 22),
            new Token(TokenKind.SymbolEquals, "=", 1, 25),
            new Token(TokenKind.LiteralInteger, "0", 1, 27),
            new Token(TokenKind.SymbolComma, ",", 1, 28),
            new Token(TokenKind.Identifier, "c2", 1, 30),
            new Token(TokenKind.SymbolEquals, "=", 1, 33),
            new Token(TokenKind.LiteralInteger, "10", 1, 35),
            new Token(TokenKind.SymbolRightCurlyBrace, "}", 1, 38),
            new Token(TokenKind.EOF, string.Empty, 1, 39)
        }));
    }

    [Test]
    public void TestFileLexing()
    {
        var assetsPath = Path.Combine(AppContext.BaseDirectory, "Assets");
        var pathToFile = Path.Combine(assetsPath, "main.z");
        var fileReader = File.OpenRead(pathToFile);
        
        var stopwatch = Stopwatch.StartNew();
        var tokens = Lexer.Tokenize(fileReader).ToList();
        var elapsed = stopwatch.ElapsedTicks;
        stopwatch.Stop();

        double nsPerTick = (1_000_000_000.0) / Stopwatch.Frequency;
        double elapsedNanoseconds = elapsed * nsPerTick;

        Console.WriteLine($"Lexing took: {elapsedNanoseconds} ns");
        foreach (var token in tokens)
        {
            Console.WriteLine(token);
        }

        Assert.Pass();
    }
    
    [TestCase("module", TokenKind.KeywordModule)]
    [TestCase("struct", TokenKind.KeywordStruct)]
    [TestCase("var", TokenKind.KeywordVar)]
    [TestCase("func", TokenKind.KeywordFunc)]
    [TestCase("defer", TokenKind.KeywordDefer)]
    [TestCase("union", TokenKind.KeywordUnion)]
    [TestCase("operator", TokenKind.KeywordOperator)]
    [TestCase("return", TokenKind.KeywordReturn)]
    [TestCase("if", TokenKind.KeywordIf)]
    [TestCase("else", TokenKind.KeywordElse)]
    public void TestKeywordTokenization(string input, TokenKind expectedKind)
    {
        var tokens = Lexer.Tokenize(input);

        Assert.That(tokens, Is.EquivalentTo(new[]
        {
            new Token(expectedKind, input, 1, 1),
            new Token(TokenKind.EOF, string.Empty, 1, input.Length + 1)
        }));
    }
}