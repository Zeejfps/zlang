using LexerModule;

namespace ParserModule.Nodes;

public sealed class LiteralIntegerNode : AstNode
{
    public Token Token { get; }
    public int Value { get; }

    public LiteralIntegerNode(Token token)
    {
        Token = token;
        Value = int.Parse(token.Lexeme);
    }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitLiteralIntegerNode(this);
    }
}